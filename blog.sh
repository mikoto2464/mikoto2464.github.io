#!/bin/bash

if test "$1" = "run"; then
  port=8080
  if [ $2 ]; then
    port=$2
  fi
  bundle exec jekyll serve --watch --host=0.0.0.0 --port=$port
elif test "$1" = "build"; then
  bundle exec jekyll build --destination=dist
elif test "$1" = "deploy"; then
  bundle exec jekyll build --destination=dist
  cos-upload local:./dist blog:/
  curl -fL -u freshCDN "https://cloud.page404.cn/api/fresh-cdn/"
elif test "$1" = "images"; then
  shift
  if test -x .venv-cos-upload/bin/python; then
    .venv-cos-upload/bin/python scripts/upload_cos_images.py "$@"
  else
    python3 scripts/upload_cos_images.py "$@"
  fi
else
  echo "usage: $0 {run [port]|build|deploy|images [--apply] [markdown ...]}"
fi
