UPDATE users
SET
    email = 'admin@aileron.com',
    display_name = 'Aileron Administrator',
    updated_at = CURRENT_TIMESTAMP
WHERE id = 'admin-user-default'
  AND (
    email <> 'admin@aileron.com'
    OR display_name <> 'Aileron Administrator'
  );
