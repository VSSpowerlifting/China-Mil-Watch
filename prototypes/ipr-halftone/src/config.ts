// src/config.ts — single entry point for site settings. Everything site-specific lives here; never hardcode in components.
import defaultOgImage from './assets/plates/default.avif';

export const site = {
  name: 'Indo-Pacific Record',
  description:
    'A source-linked record and analysis project focused on Indo-Pacific security, defense messaging, official records, and regional policy.',
  // Placeholder on purpose: this prototype is not the production site, so canonical URLs,
  // the sitemap and the feed must not claim indopacificrecord.org. Override with SITE_URL.
  url: 'https://example.com',
  locale: 'en', // BCP 47, e.g. 'en', 'ko'
  author: 'Indo-Pacific Record editors',
  // The share card for pages that carry no plate of their own (about, records, 404).
  defaultOgImage,
  // The production record: archive, corpus search and source registry. The prototype links
  // out to it rather than re-implementing it (see INTEGRATION.md, option B).
  recordUrl: 'https://indopacificrecord.org',
} as const;

export const nav = {
  header: [
    { label: 'Home', href: '/' },
    { label: 'Briefs', href: '/briefs' },
    { label: 'Desks', href: '/desks' },
    { label: 'Archive', href: '/archive' },
    { label: 'Records', href: '/records' },
    { label: 'About', href: '/about' },
  ],
  footer: [
    {
      title: 'Desks',
      links: [
        { label: 'China', href: '/china' },
        { label: 'Singapore', href: '/singapore' },
        { label: 'Regional Security', href: '/regional-security' },
        { label: 'Archive', href: '/archive' },
      ],
    },
    {
      title: 'The record',
      links: [
        { label: 'Records', href: '/records' },
        { label: 'About & methodology', href: '/about' },
        { label: 'Feed', href: '/rss.xml' },
      ],
    },
  ],
  social: [] as { label: string; href: string; icon: string }[],
} as const;

export const seo = {
  titleTemplate: '%s · Indo-Pacific Record',
  twitterHandle: '',
  jsonLd: { type: 'Organization' as 'Person' | 'Organization', name: site.name },
};

// The signature. Cover lines are the stacked, labelled teasers set on a cover
// plate: a kicker box, a headline, a short deck, one per entry.
export const coverLines = {
  overlay: true, // false lays them beside the photograph instead of on it
  divider: 'rule' as 'plus' | 'rule' | 'none',
  max: 2, // entries on the home plate; the rest print in the desk blocks below
};

export const blog = {
  postsPerPage: 4, // a desk front runs four; the fifth article starts page two
  relatedPosts: 3,
  showReadingTime: true,
};

export const features = {
  darkMode: true,
};

// Nothing is loaded until a provider is named. `id` is the site identifier the provider
// gave you: the domain for Plausible, the measurement id (G-XXXXXXX) for GA4, the website id
// for Umami. `host` is for a self-hosted install -- the origin the script is served from.
export const analytics = {
  provider: null as null | 'plausible' | 'ga4' | 'umami',
  id: '',
  host: '',
};
