// A distinct asset URL avoids the inherited favicon URL's browser cache.
const icon = document.querySelector('link[rel="icon"]');
if (icon) {
  icon.href = icon.href.replace(/\/favicon\.ico(?:\?.*)?$/, "/knora-leaf.svg");
  icon.type = "image/svg+xml";
}
