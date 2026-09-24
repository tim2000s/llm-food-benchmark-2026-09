September 2026 Diabettech article: WordPress package

1. Open preview.html locally to review the complete article and four figures.
2. Create a WordPress draft. Copy title.txt into the post title field.
3. Upload the four PNG files in figures/ to the WordPress Media Library.
4. Copy article.html into a local text editor and replace each figures/FILENAME.png
   image source with that image's full WordPress Media Library URL.
5. Add a Custom HTML block to the WordPress post and paste the amended article.html.
   The title is deliberately omitted from the body to avoid a duplicate heading.
6. Preview the post on desktop and mobile. Check all four images, the cost table
   and links before publishing. Local image paths will not work on the live site.

article.html is body-only HTML; preview.html includes styles for local review.
No publication, WordPress login or media upload is performed by this package.
The article links to the Zenodo concept DOI, which resolves to the latest version.
Affiliation: Diabettech Ltd. The linked preprint licence is CC BY 4.0.

Source: ../build/build_article.py. Rebuild with:
  python3 paper/v2/build/build_wordpress.py
Article wording and numbers are preserved. The Figure 2 caption's self-reference
was corrected to Figure 1. The HTML cost table adds an explicit currency caption.
