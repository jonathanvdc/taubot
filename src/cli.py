#!/usr/bin/env python3
import click
from accounting import LedgerServer
from accounting import parse_account_id
from bot_commands import run_command
from utils import split_into_chunks

_ver = "1.0.2"
_name = "taubot CLI"


def ps1(acc='taubot'):
    return f'{acc}> '


def cli(fp, acc):
    with LedgerServer(fp) as server:
        print(f"{_name} ver {_ver}")
        print("run help for a list of commands")
        print("or exit to leave the cli")
        while True:
            try:
                cmd = input(ps1(acc))
            except KeyboardInterrupt:
                print()
                cmd = ''
            except EOFError:
                print('exit')
                cmd = 'exit'

            if cmd == '':
                continue

            if cmd.startswith('login'):
                split = cmd.split()
                acc_id = parse_account_id(split[1])
                acc = acc_id
            elif cmd.startswith('exit'):
                break
            else:
                print(
                    run_command(acc, cmd, server))


@click.command()
@click.option("--cmd", help="cmd to run")
@click.option("--account", default="@government", help="account to run as")
@click.option("--fp", default="ledger.txt", help="fp for ledger")
def parse(cmd, account, fp):
    acc = parse_account_id(account)

    if cmd is not None:
        server = LedgerServer(fp)
        cmds = cmd.split(';')
        for cmd in cmds:

            print('\n'.join([chunk.decode("utf-8") for chunk in split_into_chunks(run_command(acc, cmd, server).encode('utf-8'), 1024)]))
        server.close()
    elif cmd is None:
        cli(fp, account)



if __name__ == "__main__":
    parse()
