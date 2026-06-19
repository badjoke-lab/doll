const MEASUREMENT_ID = "G-5NBSSFH77M";

function analyticsAllowed(request) {
  const cookie = request.headers.get("Cookie") || "";
  return cookie
    .split(";")
    .map((part) => part.trim())
    .includes("doll_analytics=granted");
}

export async function onRequest(context) {
  const response = await context.next();
  const contentType = response.headers.get("content-type") || "";

  if (!analyticsAllowed(context.request) || !contentType.includes("text/html")) {
    return response;
  }

  const snippet = `
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

  return new HTMLRewriter()
    .on("head", {
      element(element) {
        element.append(snippet, { html: true });
      },
    })
    .transform(response);
}
