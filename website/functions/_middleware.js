import {
  ALL_WRITING,
  EXTERNAL_PUBLICATIONS,
  OFFICIAL_NOTES,
  findOfficialNote,
  findWritingById,
} from "./writing-catalog.js";

const MEASUREMENT_ID = "G-5NBSSFH77M";
const PRODUCTION_HOST = "doll.badjoke-lab.com";
const SITE_URL = "https://doll.badjoke-lab.com";
const LOGO_URL = `${SITE_URL}/assets/doll-logo.png`;
const ASSET_VERSION = "20260621-1";

function analyticsAllowed(request) {
  const cookie = request.headers.get("Cookie") || "";
  return cookie
    .split(";")
    .map((part) => part.trim())
    .includes("doll_analytics=granted");
}

function isHome(pathname) {
  return pathname === "/" || pathname === "/index.html";
}

function isWritingIndex(pathname) {
  return pathname === "/writing/" || pathname === "/writing/index.html";
}

function isPrivacy(pathname) {
  return pathname === "/privacy/" || pathname === "/privacy/index.html";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function absoluteUrl(entry) {
  return entry.kind === "official" ? `${SITE_URL}${entry.path}` : entry.url;
}

function canonicalFor(pathname) {
  if (isHome(pathname)) {
    return `${SITE_URL}/`;
  }

  if (isWritingIndex(pathname)) {
    return `${SITE_URL}/writing/`;
  }

  const note = findOfficialNote(pathname);
  return note ? `${SITE_URL}${note.path}` : null;
}

function metadataFor(pathname) {
  if (isHome(pathname)) {
    return {
      title: "doll — Personal AI Continuity System",
      description: "doll is a local-complete, cloud-optional system for preserving personal AI state and ongoing work across models, runtimes, applications, providers, and machines.",
      type: "website",
      url: `${SITE_URL}/`,
    };
  }

  if (isWritingIndex(pathname)) {
    return {
      title: "Writing — doll",
      description: "Official notes and external publications about the purpose, design, risks, and development of doll.",
      type: "website",
      url: `${SITE_URL}/writing/`,
    };
  }

  const note = findOfficialNote(pathname);
  if (note) {
    return {
      title: `${note.title} — doll`,
      description: note.description,
      type: "article",
      url: `${SITE_URL}${note.path}`,
    };
  }

  if (isPrivacy(pathname)) {
    return {
      title: "Privacy — doll",
      description: "Privacy information for the doll public website, including optional analytics controls.",
      type: "website",
      url: `${SITE_URL}/privacy/`,
    };
  }

  return null;
}

function organizationData() {
  return {
    "@type": "Organization",
    "@id": `${SITE_URL}/#organization`,
    name: "badjoke-lab",
    url: SITE_URL,
    logo: LOGO_URL,
    sameAs: ["https://github.com/badjoke-lab"],
  };
}

function articleReference(entry) {
  return {
    "@type": "Article",
    headline: entry.title,
    url: absoluteUrl(entry),
    datePublished: entry.published,
  };
}

function structuredDataFor(pathname) {
  const organization = organizationData();

  if (isHome(pathname)) {
    return {
      "@context": "https://schema.org",
      "@graph": [
        organization,
        {
          "@type": "WebSite",
          "@id": `${SITE_URL}/#website`,
          name: "doll",
          url: `${SITE_URL}/`,
          description: "A local-complete, cloud-optional personal AI continuity system.",
          publisher: { "@id": `${SITE_URL}/#organization` },
          inLanguage: "en",
        },
        {
          "@type": "SoftwareSourceCode",
          "@id": `${SITE_URL}/#software`,
          name: "doll",
          description: "A personal AI continuity system that keeps user-owned state and ongoing work independent from replaceable reasoning engines and interfaces.",
          url: `${SITE_URL}/`,
          codeRepository: "https://github.com/badjoke-lab/doll",
          license: "https://www.apache.org/licenses/LICENSE-2.0",
          programmingLanguage: ["Python", "JavaScript"],
          isAccessibleForFree: true,
          image: LOGO_URL,
          creator: { "@id": `${SITE_URL}/#organization` },
          subjectOf: ALL_WRITING.map(articleReference),
        },
      ],
    };
  }

  if (isWritingIndex(pathname)) {
    return {
      "@context": "https://schema.org",
      "@graph": [
        organization,
        {
          "@type": "CollectionPage",
          "@id": `${SITE_URL}/writing/#page`,
          name: "Writing — doll",
          url: `${SITE_URL}/writing/`,
          description: "Official notes and external publications about the purpose, design, risks, and development of doll.",
          publisher: { "@id": `${SITE_URL}/#organization` },
          inLanguage: "en",
          mainEntity: {
            "@type": "ItemList",
            itemListElement: ALL_WRITING.map((entry, index) => ({
              "@type": "ListItem",
              position: index + 1,
              item: articleReference(entry),
            })),
          },
        },
      ],
    };
  }

  const note = findOfficialNote(pathname);
  if (note) {
    return {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: note.title,
      description: note.description,
      image: LOGO_URL,
      mainEntityOfPage: `${SITE_URL}${note.path}`,
      datePublished: note.published,
      dateModified: note.updated || note.published,
      author: { "@id": `${SITE_URL}/#organization` },
      publisher: organization,
      inLanguage: "en",
      isAccessibleForFree: true,
    };
  }

  return null;
}

function copyResponseWithHeaders(response, requestUrl) {
  const headers = new Headers(response.headers);

  if (requestUrl.hostname.endsWith(".pages.dev")) {
    headers.set("X-Robots-Tag", "noindex");
  }

  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

function commonHead(metadata, canonical, structuredData, noindex) {
  const faviconUrl = `/assets/doll-logo.png?v=${ASSET_VERSION}`;
  const tags = [
    `<link rel="icon" type="image/png" sizes="256x256" href="${faviconUrl}">`,
    `<link rel="shortcut icon" type="image/png" href="${faviconUrl}">`,
    `<link rel="apple-touch-icon" href="${faviconUrl}">`,
    `<link rel="manifest" href="/site.webmanifest">`,
    `<meta name="theme-color" content="#ffffff">`,
    `<link rel="alternate" type="text/plain" href="/llms.txt" title="LLM information">`,
    `<link rel="alternate" type="text/plain" href="/ai.txt" title="AI-readable site summary">`,
    `<link rel="stylesheet" href="/style.css?v=${ASSET_VERSION}">`,
    `<link rel="stylesheet" href="/writing.css?v=${ASSET_VERSION}">`,
  ];

  if (canonical) {
    tags.push(`<link rel="canonical" href="${escapeHtml(canonical)}">`);
  }

  if (noindex) {
    tags.push(`<meta name="robots" content="noindex,follow">`);
  }

  if (metadata) {
    const title = escapeHtml(metadata.title);
    const description = escapeHtml(metadata.description);
    const url = escapeHtml(metadata.url);
    tags.push(
      `<meta property="og:type" content="${escapeHtml(metadata.type)}">`,
      `<meta property="og:title" content="${title}">`,
      `<meta property="og:description" content="${description}">`,
      `<meta property="og:url" content="${url}">`,
      `<meta property="og:image" content="${LOGO_URL}">`,
      `<meta property="og:image:width" content="256">`,
      `<meta property="og:image:height" content="256">`,
      `<meta property="og:site_name" content="doll">`,
      `<meta property="og:locale" content="en_US">`,
      `<meta name="twitter:card" content="summary">`,
      `<meta name="twitter:title" content="${title}">`,
      `<meta name="twitter:description" content="${description}">`,
      `<meta name="twitter:image" content="${LOGO_URL}">`,
    );
  }

  if (structuredData) {
    tags.push(`<script type="application/ld+json">${JSON.stringify(structuredData)}</script>`);
  }

  return tags.join("\n");
}

function renderDate(entry) {
  const updated = entry.updated
    ? ` · Updated: <time datetime="${entry.updated}">${entry.updated}</time>`
    : "";
  return `Published: <time datetime="${entry.published}">${entry.published}</time>${updated}`;
}

function renderWritingEntry(entry) {
  const href = escapeHtml(absoluteUrl(entry));
  const external = entry.kind === "external-only" ? ' rel="external"' : "";
  const source = entry.kind === "external-only" ? ` · ${escapeHtml(entry.publisher)}` : "";

  return `<div class="writing-entry" data-writing-id="${escapeHtml(entry.id)}">
<p class="writing-date">${renderDate(entry)}${source}</p>
<h3><a href="${href}"${external}>${escapeHtml(entry.title)}</a></h3>
<p>${escapeHtml(entry.summary)}</p>
</div>`;
}

function renderHomeWriting() {
  const official = [...OFFICIAL_NOTES]
    .sort((left, right) => right.published.localeCompare(left.published))
    .slice(0, 2)
    .map(renderWritingEntry)
    .join("\n");
  const external = [...EXTERNAL_PUBLICATIONS]
    .sort((left, right) => right.published.localeCompare(left.published))
    .slice(0, 2)
    .map(renderWritingEntry)
    .join("\n");

  return `<section id="writing">
<h2>Writing</h2>
<p>Official notes and external publications about the purpose, design, risks, and development of doll.</p>
<h3>On this site</h3>
${official}
<h3>Elsewhere</h3>
${external}
<p><a href="/writing/">View all writing</a></p>
</section>`;
}

function renderPublicationLine(note) {
  const externalVersions = note.externalVersions.length
    ? `<p class="publication-links">Also published on ${note.externalVersions
        .map((version) => `<a href="${escapeHtml(version.url)}" rel="external">${escapeHtml(version.publisher)}</a>`)
        .join(", ")}.</p>`
    : "";

  return `<p class="publication-date">${renderDate(note)}</p>${externalVersions}`;
}

function renderRelatedWriting(note) {
  const related = note.related
    .map(findWritingById)
    .filter(Boolean);

  if (related.length === 0) {
    return "";
  }

  return `<section class="related-writing">
<h2>Related writing</h2>
${related.map(renderWritingEntry).join("\n")}
</section>`;
}

export async function onRequest(context) {
  const originalResponse = await context.next();
  const requestUrl = new URL(context.request.url);
  const response = copyResponseWithHeaders(originalResponse, requestUrl);
  const contentType = response.headers.get("content-type") || "";

  if (!contentType.includes("text/html")) {
    return response;
  }

  const note = findOfficialNote(requestUrl.pathname);
  const metadata = metadataFor(requestUrl.pathname);
  const canonical = canonicalFor(requestUrl.pathname);
  const structuredData = structuredDataFor(requestUrl.pathname);
  const isProduction = requestUrl.hostname === PRODUCTION_HOST;
  const shouldAddAnalytics = isProduction && analyticsAllowed(context.request);
  const privacyPage = isPrivacy(requestUrl.pathname);
  const noindex = privacyPage || requestUrl.hostname.endsWith(".pages.dev") || response.status === 404;

  const analyticsSnippet = `
<script async src="https://www.googletagmanager.com/gtag/js?id=${MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){dataLayer.push(arguments);}
  gtag('js', new Date());
  gtag('config', '${MEASUREMENT_ID}', {
    allow_google_signals: false,
    allow_ad_personalization_signals: false
  });
</script>`;

  const privacyControls = `
 / <a href="/privacy/">Privacy</a>
 / <button type="button" class="link-button" data-analytics-settings>Analytics settings</button>`;

  let rewriter = new HTMLRewriter()
    .on("head", {
      element(element) {
        element.append(commonHead(metadata, canonical, structuredData, noindex), { html: true });

        if (shouldAddAnalytics) {
          element.append(analyticsSnippet, { html: true });
        }

        if (!privacyPage) {
          element.append(`<script defer src="/analytics-consent.js?v=${ASSET_VERSION}"></script>`, { html: true });
        }
      },
    });

  if (metadata) {
    rewriter = rewriter
      .on("title", {
        element(element) {
          element.setInnerContent(metadata.title);
        },
      })
      .on('meta[name="description"]', {
        element(element) {
          element.setAttribute("content", metadata.description);
        },
      });
  }

  if (!privacyPage) {
    rewriter = rewriter.on("footer p", {
      element(element) {
        element.append(privacyControls, { html: true });
      },
    });
  }

  if (isHome(requestUrl.pathname)) {
    let sectionCount = 0;
    rewriter = rewriter
      .on(".site-links", {
        element(element) {
          element.append(' / <a href="/writing/">Writing</a>', { html: true });
        },
      })
      .on("main > section", {
        element(element) {
          sectionCount += 1;
          if (sectionCount === 4) {
            element.before(renderHomeWriting(), { html: true });
          }
        },
      })
      .on('footer a[href="./notes/ai-will-remain/"]', {
        element(element) {
          element.setAttribute("href", "/writing/");
          element.setInnerContent("Writing");
        },
      });
  }

  if (note) {
    let headingCount = 0;
    rewriter = rewriter
      .on('body > p a[href="../../"]', {
        element(element) {
          element.setAttribute("href", "/writing/");
          element.setInnerContent("Back to Writing");
        },
      })
      .on("article > h2", {
        element(element) {
          headingCount += 1;
          if (headingCount === 1) {
            element.after(renderPublicationLine(note), { html: true });
          }
        },
      })
      .on("article", {
        element(element) {
          const related = renderRelatedWriting(note);
          if (related) {
            element.append(related, { html: true });
          }
        },
      });
  }

  return rewriter.transform(response);
}
