#!/usr/bin/env python3
import click
from accounting import SQLServer
from accounting import parse_account_id
from bot_commands import run_command
from prompt_toolkit.history import FileHistory
from prompt_toolkit import PromptSession

_ver = "2.0.0"
_name = "taubot CLI"
_history = FileHistory(".history")
_session = PromptSession(history=_history, )


def ps1(acc='@government'):
    return f'{acc}> '


def cli(acc, kwargs):
    with SQLServer(**kwargs) as server:
        print(f"{_name} ver {_ver}")
        print("run help for a list of commands")
        print("or exit to leave the cli")
        while True:
            try:
                cmd = _session.prompt(ps1(acc))
            except KeyboardInterrupt:
                cmd = ''
            if cmd == '':
                continue

            if cmd.startswith('login'):
                split = cmd.split()
                acc_id = parse_account_id(split[1])
                acc = acc_id
            elif cmd.startswith('exit'):
                break
            else:
                print(run_command(acc, cmd, server))


@click.command()
@click.option("--cmd", help="cmd to run")
@click.option("--account", default="@government", help="account to run as")
@click.option("--url", help="the url for the database")
@click.option("--uname", help="the username to connect with")
@click.option("--psswd", help="psswd used to connect to the database")
@click.option("--db")
@click.option("--dialect")
def parse(cmd, account, **kwargs):
    acc = parse_account_id(account)

    if cmd is not None:
        server = SQLServer(**kwargs)
        cmds = cmd.split(';')
        for cmd in cmds:
            print(run_command(acc, cmd, server))
        server.close()
    elif cmd is None:
        cli(account, kwargs)


if __name__ == "__main__":
    parse()
