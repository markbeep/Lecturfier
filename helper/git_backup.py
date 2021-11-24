import subprocess

from helper.log import log


def gitpush(directory):
    """
    Commits and pushes a git directory
    :param directory: directory to commit and push
    :return: commit and push message
    """
    commit_out = subprocess.run(["git", "-C", directory, "commit", "-a", "-m", "Update"])
    log(f"Commited: {commit_out}", "GIT")
    push_out = subprocess.run(["git", "-C", directory, "push", "-u"])
    # git -C ./data push -u origin main
    log(f"Pushed: {push_out}", "GIT")
    return commit_out.returncode, push_out.returncode
