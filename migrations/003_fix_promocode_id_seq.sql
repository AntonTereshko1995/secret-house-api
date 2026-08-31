-- Reset the promocode.id sequence to max(id) so that autoincrement inserts
-- don't collide with rows that were imported with explicit id values.
-- setval with is_called=true means nextval() returns max(id)+1.
SELECT setval(
    pg_get_serial_sequence('promocode', 'id'),
    COALESCE((SELECT MAX(id) FROM promocode), 1)
);
