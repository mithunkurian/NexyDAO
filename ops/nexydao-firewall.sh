#!/bin/sh
# Root-owned, narrowly scoped host guard. Never flush another table or change SSH.
set -eu
umask 077
rules=$(mktemp)
trap 'rm -f "$rules"' EXIT HUP INT TERM
if /usr/sbin/nft list table inet nexydao_guard >/dev/null 2>&1; then
    printf 'delete table inet nexydao_guard\n' > "$rules"
fi
cat >> "$rules" <<'NFT'
table inet nexydao_guard {
    chain input {
        type filter hook input priority -20; policy accept;
        iifname != "lo" tcp dport { 4001, 4002, 5000, 5901, 7496, 7497 } drop
    }
}
NFT
/usr/sbin/nft --check --file "$rules"
# One atomic transaction replaces only our table. A failed check keeps old rules.
/usr/sbin/nft --file "$rules"
