CREATE TABLE IF NOT EXISTS accounts
(
    uuid char(36) primary key,
    auth integer,
    balance integer,
    frozen BOOLEAN,
    public BOOLEAN,
    name varchar
);

CREATE TABLE IF NOT EXISTS tax
(
    uuid char(36) primary key,
    rate integer,
    start integer,
    stop integer
);

CREATE TABLE IF NOT EXISTS proxies
(
    controller char(36),
    controllee char(36)
);

SELECT * FROM accounts;