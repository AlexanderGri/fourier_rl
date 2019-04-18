#! /bin/env python
import os
import os.path
import sys
import subprocess
import argparse


def get_hostname():
    result = subprocess.run(['hostname'], stdout=subprocess.PIPE)
    hostname = result.stdout.decode().strip()
    return hostname


def write_preamble(outF):
    hostname = get_hostname()
    outF.write('# !/bin/sh\n')
    outF.write(f'# BSUB -q {QUEUES[hostname]}\n')
    outF.write(f'# BSUB -n {CPU_PER_JOB}\n')
    outF.write('# BSUB -J povt\n')
    outF.write(f'# BSUB -gpu "num={GPU_PER_JOB}:mode=shared:j_exclusive=yes"\n')
    outF.write('# BSUB -o %J.out\n')
    outF.write('# BSUB -e %J.err\n')
    if ONLY_MLL_HOSTS and IS_SAIC:
        outF.write('# BSUB -m "airugpua03 airugpua04 airugpub02"\n')
    outF.write("export OMP_NUM_THREADS=1\n")
    outF.write("export MKL_NUM_THREADS=1\n")
    outF.write(f'. activate {ENVS[hostname]}\n')


def parse_args():
    parser = argparse.ArgumentParser(description="Run POVT on cluster")
    parser.add_argument('--n_seeds', type=int, help='Number of seeds for an environemnt. Default: 4 for MHike and 3 for Atari.')
    parser.add_argument('--n_per_job', type=int, help='Number of runs per job. Default: 4 for MHike and 1 for Atari.')
    args = parser.parse_args()
    if args.n_seeds is None:
        args.n_seeds = 4
    if args.n_per_job is None:
        args.n_per_job = 4
    return args


def calculate_schedule(n_seeds, n_per_job):
    n_jobs = (n_seeds + n_per_job - 1) // n_per_job
    per_job_short = n_seeds // n_jobs
    n_long_jobs = n_seeds % n_jobs
    return [per_job_short + 1] * n_long_jobs + [per_job_short] * (n_jobs - n_long_jobs)


SAIC='airulsf01'
JL='jlrulsf01'
IS_SAIC = (get_hostname() == SAIC)
ONLY_MLL_HOSTS=False
GPU_PER_JOB=1
CPU_PER_JOB=1

QUEUES = {
    SAIC: 'mll',
    JL: 'Q_HSE'
}

ENVS = {
    SAIC: 'povt_2',
    JL: 'dvrl'
}

USE_DOCKER=True
DOCKER_IMAGE='arseny_k/rlkit:1'

args = parse_args()
params = {
    # 'sample.param' : None,
    # 'replay_buffer_conf.max_size' : 1000,
    # 'replay_buffer_conf.min_size' : 800
}

cur_folder = os.getcwd()
options = ' '.join(["{}={}".format(k,v) for (k, v) in params.items() if v is not None]) 
if USE_DOCKER:
    command = 'python {}/sac.py {}'.format('/home/docker/repo', options)
else:
    command = 'python {}/sac.py {}'.format(cur_folder, options)

for job_id, n_seeds in enumerate(calculate_schedule(args.n_seeds, args.n_per_job)):
    with open('.submit_batch', 'w') as outF:
        write_preamble(outF)
        if USE_DOCKER:
            outF.write('python shepherd.py {} {}'.format(DOCKER_IMAGE, ' '.join([f'"{command}"'] * n_seeds)))
        else:
            for seed_id in range(n_seeds):
                outF.write(command + ' & \n')
    subprocess.call('bsub', stdin=open('.submit_batch'))

