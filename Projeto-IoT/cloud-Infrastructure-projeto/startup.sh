#!/bin/bash

exec jupyter notebook --ip=0.0.0.0 --port 8888 --allow-root --no-browser --notebook-dir=/home --NotebookApp.token='' --NotebookApp.password=''
