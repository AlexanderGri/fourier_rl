import docker
import docker.errors
import os
import platform
import time
import signal
import sys
import subprocess


class ContainerShepherd:
    def __init__(self, image, parallel_commands):
        self._image = image
        self._parallel_commands = parallel_commands
        self._client = docker.from_env()
        self._containers = []
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_violently)

    def log_iterator(self):
        for cont in self._containers:
            stdout_log_entry = cont.logs(stdout=True, stderr=False)
            stderr_log_entry = cont.logs(stdout=False, stderr=True)
            yield stdout_log_entry.decode("utf-8"), stderr_log_entry.decode("utf-8")

    @staticmethod
    def is_container_finished(container):
        container.reload()
        return container.status == 'exited'

    def all_finished(self):
        return all([self.is_container_finished(cont) for cont in self._containers])

    def pull_image(self):
        if platform.node().startswith('ai'):
            docker_repo_server = 'airuhead01:5000'
        else:
            docker_repo_server = 'jlruhead01:5000'
        self._image = docker_repo_server + '/' + self._image
        self._client.images.pull(self._image)

    def get_CVD(self):
        current_devices = subprocess.check_output(['nvidia-smi', '--query-gpu=uuid', '--format=csv,noheader'])
        current_devices = current_devices.decode('utf-8').strip().split('\n')
        all_devices = self._client.containers.run(self._image,
                                                  ['nvidia-smi', '--query-gpu=uuid', '--format=csv,noheader'],
                                                  remove=False, runtime='nvidia')
        all_devices = all_devices.decode('utf-8').strip().split('\n')
        cuda_visible_devices = [all_devices.index(cd) for cd in current_devices]
        return ",".join([str(i) for i in cuda_visible_devices]) 

    def run(self):
        self.pull_image()
        volumes = {
            os.getcwd(): {'bind': '/home/docker/repo', 'mode': 'rw'}
        }
        environment = {'CUDA_VISIBLE_DEVICES': self.get_CVD()}

        for cmd in self._parallel_commands:
            try:
                time.sleep(1.5)
                cont = self._client.containers.run(self._image, cmd, remove=False, detach=True,
                                                   volumes=volumes, runtime='nvidia', environment=environment,
                                                   user='{}:{}'.format(os.getuid(), os.getgid()))
                self._containers.append(cont)
            except docker.errors.APIError as e:
                self.exit_gracefully(None, None)
                time.sleep(5)
                self.exit_violently(None, None)
                raise e
        while True:
            time.sleep(1)
            if self.all_finished():
                self.write_output()
                self.clean_containers()
                return

    def write_output(self):
        for stdout_logs, stderr_logs in self.log_iterator():
            sys.stdout.write(stdout_logs)
            sys.stderr.write(stderr_logs)

    def exit_gracefully(self, signum=None, frame=None):
        for cont in self._containers:
            cont.kill('SIGINT')

    def exit_violently(self, signum=None, frame=None):
        for cont in self._containers:
            cont.stop(timeout=0)

    def clean_containers(self):
        for cont in self._containers:
            cont.remove()


def main():
    image_name = sys.argv[1]
    parallel_commands = sys.argv[2:]
    shepard = ContainerShepherd(image_name, parallel_commands)
    shepard.run()


if __name__ == '__main__':
    main()
