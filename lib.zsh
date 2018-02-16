
# This directory.
here=${0:a:h}
exe="$here/lib.py"

lib() {
  if [[ $1 == "cd" ]]; then
    cd $($exe where ${@:2})
  else
    $exe $@
  fi
}
