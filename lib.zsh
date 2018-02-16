
# Get script's directory.
here=${0:a:h}

# If the script is a symlink, we want to follow the symlink back to we can
# access the executable.
if [ -h $0 ]; then
  here=$(dirname $(readlink $0))
fi

# Path to executable.
exe="$here/lib.py"

# Wrap lib executable to allow for cd functionality.
lib() {
  if [[ $1 == "cd" ]]; then
    cd $($exe where ${@:2})
  else
    $exe $@
  fi
}
