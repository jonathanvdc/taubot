#!/usr/bin/env bash

if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root" >&2 
   exit 1
fi



echo "Detecting OS"
if [[ -f /etc/os-release ]]; then
    . /etc/os-release;
else
    echo "Couldn't get OS info"
    exit 1
fi


echo "Installing dependencies"
if [[ "$ID_LIKE" == "debian" ]]; then
    apt-get update
    apt-get install postgresql libpq-dev postgresql-client postgresql-client-common

elif [[ "$ID" == "opensuse-tumbleweed" ]]; then
    # TODO: add support for openSUSE leap
    zypper -n addrepo -f http://download.opensuse.org/repositories/server:database:postgresql/openSUSE_Tumbleweed/ PostgreSQL
    zypper -n --gpg-auto-import-keys refresh
    zypper -n install postgresql postgresql-server postgresql-contrib
else 
    echo "Your Distrubution is not supported, assuming you already have postgresql installed"
fi

systemctl enable postgresql
systemctl start postgresql



echo "setting up the database"
sudo -u postgres createuser taubot -dP

sudo -u postgres createdb taubot

echo "installing python dependencies"
pip3 install -r ../requirements.txt

echo "Done!"
