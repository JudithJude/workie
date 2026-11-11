from . import arbeitnow, ats, bundesagentur, firecrawl_pages

ALL = {
    "arbeitnow": arbeitnow.fetch,
    "bundesagentur": bundesagentur.fetch,
    "ats": ats.fetch,
    "firecrawl": firecrawl_pages.fetch,
}
