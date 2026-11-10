# Handoff, 9 Nov 2026

For the next working session on The Point of Failure. Read this page, then
docs/PLAYBOOK.md (all of it), before touching anything.

## The channel in one paragraph

A free, automated YouTube channel explaining engineering disasters with our
own 3D (Blender, src/kits/*_3d.py) and 2D (src/kits/*.py, drawn line by line)
plus real public-domain photos. Seven long videos and six Shorts are out.
Shorts reach 1,200 to 1,700 people each; long videos get 8 to 141 views.
The owner's goal: "build the best animation ever", so that people are stunned
by the picture. Our edge over big channels (Sabin Civil Engineering): the
investigation's facts and real material. Our gap: the opening, shot length,
the collapse itself, sound, and thumbnails people click.

## Rules that never bend (also in the playbook, section 1)

- Never touch the shadow-archives-bot repository. No paid services. Free,
  public-domain or CC material only; credits in the description.
- Secrets live only in GitHub Secrets; never print them, never ask for them
  in chat. The repo stays public. No pull requests unless asked; work on
  `main`.
- Never use .github/workflows/fetch_artifact.yml. Never set PIPELINE_ENABLED.
- No model name in commits, code or videos.
- Facts only, no race or politics. Never photos of the dead or remains,
  never a victim's last moments.
- No AI-generated video. Leave YouTube's AI/synthetic question unanswered.
- No picture shown twice. Nothing frozen in the 3D; the 2D builds line by
  line. Clips are preferred to stills.
- The owner reviews every video before upload. Never delete and re-upload a
  public video. Published videos (titles included) are not touched.
- Search-first titles: "[Name] [Collapse/Disaster] ([year]): [hook]", under
  65 characters.
- Keep docs/PLAYBOOK.md updated after every video and every readout.
- The owner's insulting comment replies stay (their personality).

## How things run

- Long video: `episode_sample.yml` (renders 3D in shards, the 2D, voice,
  assembles; `rerender: FIRST-LAST` re-renders only a frame range and
  patches it in). Review copies go to the `preview-media` branch.
  Publish: `publish_episode.yml` (run_id, title, thumbs, publish_at).
- Short: `short_story.yml` with tools/story_short.py and
  shorts/<short>/script.json on preview-media. `from_run` publishes the
  reviewed copy as is. It fails on any still stretch (tools/stillness.py).
- Upload spacing: src/upload_gate.py (24 h since 10 Nov; three long videos a week).
- Thumbnail rotation: `rotate_thumbnails.yml`, branch `thumb-rotation`.
- youtube.com is blocked from the sessions; vidIQ is out of credits. Numbers
  come from the owner's Studio screenshots.

## The upgrade: what to change, specifically

Published videos stay as they are. The upgrade goes into the pipeline, and
it is proved on a **private review copy of the Silver Bridge long video**
rebuilt with every change below. Send it to the owner side by side with the
published one before any new topic is built.

1. **Opening, first 5 seconds = the disaster, moving.**
   - Remove the "STAY TO THE END" card (tools/preview.py around line 179),
     the black gap and the title card that sit before the story (0:04 to
     0:15 on Silver Bridge; 3 of 18 viewers left there).
   - Frame 1: the fall itself (real film when it exists, else our 3D fall,
     close), with one big line, as the Shorts now do. The title can ride
     over moving picture later, never on its own card.
2. **No shot longer than about 8 seconds, anywhere.**
   - 3D: more `shot(...)` cuts in each kit's camera list
     (src/kits/eyebar_chain_3d.py around line 329 shows the form); cuts cost
     no extra render.
   - 2D: cut each long kit clip (build 38 s, physics 52 s, compare 40 s,
     timeline 57 s on Silver Bridge) into steps of 4 to 8 s, each with its
     own framing: wide, then close on the part, then the label. The zoom and
     crop already used in tools/story_short.py (`_cover` with zoom and a
     slow push) is the model.
   - Photos (src/episode.py, ARCHIVE slots aftermath and today_photos):
     6 to 8 s each with movement; if there are not enough distinct photos,
     the slot gets shorter or gets 3D or 2D instead. Never one photo for
     24 s.
   - The ending: no 37-second text card. Pictures, a closing question, the
     next video.
   - Add an automatic check that fails the build like the Shorts' stillness
     check: any shot over 8 s, or any stretch over 3 s where the picture
     barely changes.
3. **The collapse is the centrepiece.** Today it is a 12-second distant
   shot at 3:34 with no splash and no cars falling. Make it 30 to 60 s,
   step by step, close: the joint parting, the chain letting go, the tower
   tipping, spans and cars into the river, splashes, from 6 to 10 angles of
   4 to 6 s each.
4. **Sound for every scene,** as well as the music: rain on the joint,
   steel straining, the snap, the splash, water after. The Shorts' score
   already has lock, crash, boom, ping and groan; extend it and use it in
   the long-video mix shot by shot.
5. **The 3D finish (src/kits/look.py):** the piers and hills read as flat
   blocks and sand; the cars are boxes. Give concrete and steel texture,
   rust at the joints, wheels and windows on the cars, mist on the water.
   Keep render time inside GitHub's 3-hour jobs (shards).
6. **A question before each answer,** every 30 to 60 s ("Where would water
   collect?" works).
7. **Thumbnails built on curiosity, not wreckage.** The postcard thumbnail
   got 2.5% clicks against Teton's 6.5%. Sabin's shows a 1927 car beside a
   1967 car. Make 3 to 4 options per video, share them with the owner, and
   rotate them.

Shorts already follow the new rules (playbook 6b). Keep them.

## Waiting on the owner

- Go on the next topic. Proposed: **Tacoma Narrows Bridge (1940)**: real
  1940 film of the twisting deck, widely described as public domain (check
  each clip's licence on its archive page before use), about 31K searches a
  month and growing, no human victims. Runner-up: Vajont (1963).
- Their list of corrections to the Silver Bridge long video (never sent).
- Whether to move to three long videos a week (Mon, Wed, Fri; each Short the
  next day; Sunday off). If yes: the upload gate goes from 48 h to 24 h.
- They set "Related video" on each Short in Studio themselves.

## Readouts due

- E1, Teton thumbnail rotation: about 11 Nov.
- E4, Silver Bridge Short (9jel8N8tNNc): about 14 Nov, against Teton's 51.9%
  "stayed to watch" and the drop at 0:04.5 to 0:07.
- Silver Bridge long (foZj6XFlEKc): readout in the playbook (E3). Retention
  held up (about 66% at 0:30); clicks did not (2.5%).
