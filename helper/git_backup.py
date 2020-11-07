import subprocess
from helper.log import log


def gitpush(directory):
    """
    Commits and pushes a git directory
    :param directory: directory to commit and push
    :return:
    """
    commit_out = subprocess.run(["git", "-C", directory, "commit", "-a", "-m", "Update"])
    push_out = subprocess.run(["git", "-C", directory, "push", "-u", "origin", "main"])
    log(f"Commited: {commit_out}", "GIT")
    log(f"Pushed: {push_out}", "GIT")
