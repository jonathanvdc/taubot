#!/usr/bin/env bash
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi
echo "installing dependencies"
apt-get install postgresql libpq-dev postgresql-client postgresql-client-common

echo "setting up the database"
if [[ $# -eq 0 ]]
then
  sudo -u postgres createuser taubot -dP
else
  sudo -u postgres createuser taubot -d
  sudo -u postgres psql -c "ALTER USER taubot WITH PASSWORD '"$0"';"
fi
sudo -u postgres createdb taubot
sudo -u postgres createdb taubot-tests

echo "installing python dependencies"
pip3 install -r ../requirements.txt

echo "Done!"