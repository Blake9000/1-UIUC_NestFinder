A3:
We have 2 APIs at apartments/api/ and subleases/api/. These APIs release all of the listings we have of the particular sort. They both respond with JSON.

UI description - 
Our primary site will focus on 2 things. On the left, filling about 1/3 of the screen is a list of apartment and sublease listings. On the right, filling the rest of the 2/3 will be an interactive map.
The map has not been implemented yet and currently is being used a spot to demonstrate the server-side graph. Once this week is graded, we will remove the map and work on implementing an interactive map using 
a JS library of some sort. Apartments will be shown and selectable through this map.

URL linking and navigation -
We separated URLs into each respective app. In the HTML, the links are referenced using the link name or get_absolute_url instead of hardcoding. This will future-proof our project and prevent small changes to views or URLs needing
tons of revisions elsewhere. The home page will be our listings. Our detail page is demonstrated by clicking on view details on this listing page. This link, which uses get_absolute_url, shows additional information about the property.