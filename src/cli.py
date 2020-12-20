#!/usr/bin/env python3
import click
from accounting import SQLServer
from accounting import parse_account_id
from bot_commands import run_command


_ver = "1.0.2"
_name = "taubot CLI"


def ps1(acc='taubot'):
    return f'{acc}> '


def cli(psswd, acc):
    with SQLServer(psswd=psswd) as server:
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
@click.option("--psswd", help="psswd used to connect to the database")
def parse(cmd, account, psswd):
    acc = parse_account_id(account)

    if cmd is not None:
        server = SQLServer(psswd)
        cmds = cmd.split(';')
        for cmd in cmds:

            print(run_command(acc, cmd, server))
        server.close()
    elif cmd is None:
        cli(psswd, account)



if __name__ == "__main__":
    parse()
