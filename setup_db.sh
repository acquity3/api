#!/usr/bin/env bash
sudo -u postgres psql -c "DROP DATABASE acquity"
sudo -u postgres psql -c "DROP DATABASE acquity_test"
sudo -u postgres psql -c "DROP ROLE acquity"
sudo -u postgres psql -c "CREATE ROLE acquity WITH LOGIN PASSWORD 'acquity'"
sudo -u postgres psql -c "CREATE DATABASE acquity"
sudo -u postgres psql -c "CREATE DATABASE acquity_test"
