from accounting import LedgerServer
from accounting import parse_account_id
from bot_commands import run_command
from bot import read_config

_ver = 1.0
_name = "taubot CLI"


def ps1(acc='taubot'):
    return f'{acc}> ' if acc else 'taubot> '


if __name__ == "__main__":
    config = read_config()
    # CLI start
    with LedgerServer('ledger.txt') as server:
        print(f"{_name} ver {_ver}")
        acc = parse_account_id('@government')
        while True:
            cmd = input(ps1(acc))+' '
            if cmd.startswith('login '):
                split = cmd.split()
                acc_id = parse_account_id(split[1])
                acc = acc_id
            elif cmd.startswith('exit '):
                break
            else:
                print(
                    run_command(acc, cmd, server))
