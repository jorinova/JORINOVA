# User profile photos

Drop user profile photos here. The DB column `users.profile_photo` holds
the URL/path; the `Avatar` component (`frontend/app/components/Avatar.tsx`)
reads it from the `/me` endpoint via `user.photo_url`.

## Convention

For a user whose `profile_photo` column is set to `/profiles/admin.jpg`,
save the file at:

```
D:\JORINOVA NEXUS\frontend\public\profiles\admin.jpg
```

Next.js serves anything under `public/` at the root URL, so the file is
reachable from the browser at `http://localhost:3000/profiles/admin.jpg`.

## Conventions

| Username | File name | DB pointer |
|---|---|---|
| admin | `admin.jpg` | `/profiles/admin.jpg` |
| labmanager | `labmanager.jpg` | `/profiles/labmanager.jpg` |
| (any other) | `<username>.jpg` | `/profiles/<username>.jpg` |

## Sizing

- Square, at least **200 × 200 px**. The component crops/scales.
- JPEG for photos, PNG for transparent badges. Keep under 500 KB.

## If the file is missing

`<Avatar>` automatically falls back to a coloured circle with the user's
initials — no broken-image icon. So you can roll out users gradually,
adding their photos one at a time.
