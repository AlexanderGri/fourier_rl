#!/bin/env python

import sys
import os
import shutil

for f in os.listdir('.'):
    if f.endswith('err') or f.endswith('out'):
        os.remove(f)

for f in os.listdir('data'):
    shutil.rmtree(os.path.join('data', f))
