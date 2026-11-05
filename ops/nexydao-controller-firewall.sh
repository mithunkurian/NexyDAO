#!/bin/sh
# Root-owned guard for one dedicated UID; do not flush host or ingress rules.
set -eu
umask 077
[ "$(/usr/bin/id -u)" -eq 0 ] || exit 1
controller_uid=$(/usr/bin/id -u nexydao-controller)
case "$controller_uid" in ''|*[!0-9]*|0) exit 1 ;; esac
rules=$(mktemp)
trap 'rm -f "$rules"' EXIT HUP INT TERM
if /usr/sbin/nft list table inet nexydao_controller_guard >/dev/null 2>&1; then
    printf 'delete table inet nexydao_controller_guard\n' > "$rules"
fi
cat >> "$rules" <<NFT
table inet nexydao_controller_guard {
    chain output {
        type filter hook output priority -20; policy accept;
        meta skuid $controller_uid tcp dport { 22, 4001, 4002, 5000, 5901, 7496, 7497 } drop
    }
}
NFT
/usr/sbin/nft --check --file "$rules"
/usr/sbin/nft --file "$rules"
