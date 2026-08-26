# Midland sales photo tagging

Tagging the sales photo library so marketing and sales can find images. Filenames are
mostly camera defaults and carry no meaning.

**Scope: `sites/SalesMarketingTeam/Shared Documents/Sales/1. Trailer Photos` only.**

## Read in this order

1. `findings/library-structure.md` — what is actually in the library, and why
   enumeration has to recurse
2. `routines/01-enumeration.md` — the free pass that builds the work queue. Runs first
3. `schema/trailer-photo-tags.schema.json` — the tag record
4. `routines/02-thursday-iteration.md` — how the schema gets frozen before any volume

`findings/join-discovery.md` is parked: it records that photo folder job numbers join
exactly to the Manufacturing Job Cards, which is out of scope for now but cheap when
wanted.

## House vocabulary

A trailer with two axles is a **Tandem**. Never "bogie". Midland's own folders read
`2. Tandem Axle Tag Trailer`. A general model reaches for "bogie" constantly on
Australian trailer photos, so the prohibition is stated explicitly in every prompt and
the word appears in no enum.

## Two rules the schema exists to enforce

- **Never ask a model for what the path already says.** Product category, variant, axle
  configuration, customer, build date and job number are all in the folder path. They
  are parsed, not inferred.
- **Every field accepts `unknown`.** A model forced to always emit a value invents one,
  and invented specifications are what made the first attempt read as garbage.
