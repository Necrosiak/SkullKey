# Community bug hunters

People who reported, diagnosed or helped fix bugs in SkullKey — thank you!

A report that says *what* broke is useful. The entries below went further: the
detail that ruled out the obvious explanation, the environment nobody had
tested on, the insistence that something was still broken after a fix that was
not quite right.

If you reported something and are not listed here, that is an oversight —
please say so on an [issue](https://github.com/Necrosiak/SkullKey/issues).

---

### [@arsaban](https://github.com/arsaban)

- The Genshin Impact mod-loading request, and the testing that mapped out what
  SkullKey could and could not reasonably do about third-party mod loaders
  ([#1](https://github.com/Necrosiak/SkullKey/issues/1))

### [@tobal37](https://github.com/tobal37)

- Store authentication failing on CachyOS: the report that surfaced two separate
  causes — store logins that could not complete without a terminal, and `gogdl`
  failing to build its native extension on Python 3.14, which broke GOG
  provisioning outright while the ensure task still reported success
  ([#3](https://github.com/Necrosiak/SkullKey/issues/3), fixed in v1.12.1 and
  v1.12.2)
