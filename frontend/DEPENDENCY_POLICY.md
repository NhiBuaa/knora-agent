# Frontend dependency policy

M5.2 does not use `next/image` or server-side image processing. Next.js may still install
the optional `sharp` packages, including platform-specific `@img/sharp-*` and
`@img/sharp-libvips-*` packages, as part of its standard dependency tree.

These packages are retained as transitive optional dependencies so the lockfile remains
reproducible across supported build platforms. The application sets `images.unoptimized` and
does not import Sharp directly. The current license scanner findings for these optional packages
are therefore recorded as an accepted, scoped exception for M5.2, not as an application runtime
dependency or an enabled image-processing feature.

Revisit this exception before enabling `next/image`, image optimization, or any server-side image
processing. At that point, review the selected Sharp/libvips licenses and deployment obligations
again, and replace or remove the exception if the dependency becomes part of the product runtime.
