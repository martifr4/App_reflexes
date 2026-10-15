# Calame — website

One-page website for calame-ia.ch, in French and English. Static files only: no build step, no cookies,
no trackers, nothing loaded from other websites (not even fonts).

| File | What it is |
|---|---|
| `index.html` | French page (the homepage) |
| `en.html` | English page |
| `style.css` | Look and layout, shared by both pages |
| `favicon.svg` | The small icon shown in the browser tab |
| `robots.txt` | Tells search engines they may read the site, and where the sitemap is |
| `sitemap.xml` | List of the site's pages, for Google and Bing |

Total size: about 50 KB (the Web Starter limit is 10 MB).

## Preview on your own computer

Download all the files into the same folder and double-click `index.html`. It opens in your browser.

## Publish on Infomaniak (Web Starter)

### 1. Download the files

1. On GitHub, open the repository and switch to the branch that holds the site.
2. Open the `calame` folder.
3. Click `index.html`, then the **Download raw file** button (the arrow pointing down, top right of the file).
4. Do the same for `en.html`, `style.css`, `favicon.svg`, `robots.txt` and `sitemap.xml`.
5. Check that all six files are in your Downloads folder and that the names are exactly
   `index.html`, `en.html`, `style.css`, `favicon.svg`, `robots.txt` and `sitemap.xml`. Some browsers add `.txt` to the end. If yours did, rename the file.

### 2. Open the file manager in Infomaniak

1. Go to https://manager.infomaniak.com and log in.
2. Open the **Web & Domain** section. You can reach it from the grid icon at the top of the page.
3. Click **Hosting**.
4. Click the name of your hosting for calame-ia.ch.
5. In the left-hand menu, click **FTP / SSH**.
6. Click the **Web FTP** button. A file manager opens in a new tab.
   Your Infomaniak login is enough, so you don't need a separate FTP password.

### 3. Find the folder your website is served from

1. You'll see a list of folders. Open the one called **web**.
2. If there is no `web` folder, look for the folder that already contains a file called
   `index.html` or `index.php`. That one is the site's main folder.
3. If you can't tell which folder it is, stop and ask before uploading anything.

### 4. Upload the files

1. If an `index.html` or `index.php` from Infomaniak (their placeholder page) is already there,
   delete it or rename it to `old-index.html`.
   Renaming is the safer choice because you can undo it.
2. Drag all six files from your Downloads folder into the Web FTP window.
3. Wait until all six files show in the list. If asked whether to replace existing files, say yes.

### 5. Check the live site

1. Open https://calame-ia.ch in a new browser tab. If you still see the old page,
   press Ctrl+F5 (Windows) or Cmd+Shift+R (Mac) to reload it.
2. Open it on your phone too.
3. Click **Réserver un diagnostic gratuit**. Your email app should open, addressed to marti@calame-ia.ch.

If the site doesn't show up at all, the domain may not point to the hosting yet.
Contact Infomaniak support. They respond in English and French.

## Updating the site later

Change the file and upload it again in step 4. It replaces the old one.
If you change the text, change it in both `index.html` (French) and `en.html` (English).

Don't delete the `google….html` file from Google Search Console: it proves to Google that the site is yours.
