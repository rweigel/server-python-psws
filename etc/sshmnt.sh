mount_dir="$HOME/sshfs/psws"
uname="rweigel"
if mount | grep -Fq " on $mount_dir ("; then
	if ! sudo diskutil unmount force "$mount_dir"; then
		printf 'Failed to unmount %s; skipping sshfs mount.\n' "$mount_dir" >&2
		exit 1
	fi
fi

sshfs "$uname"@pswsnetwork.eng.ua.edu:/home "$mount_dir" -o reconnect,ServerAliveInterval=15,ServerAliveCountMax=3
