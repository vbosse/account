drop table if exists account_entries;
create table account_entries (
  id integer primary key autoincrement,
  account_id text not null,
  date date not null,
  description text not null,
  category text not null,
  amount integer not null,
  type integer not null,
  is_checked integer not null,
);

