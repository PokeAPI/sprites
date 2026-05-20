const imgRe = /https:\/\/raw\.githubusercontent\.com\/PokeAPI\/sprites\/[\/-\w\d]+\/[\d\w-]+\.(?:png|svg|gif)/
const version = 1

self.addEventListener('fetch', function (event) {
    if (event.request.url.match(imgRe)) {
        event.respondWith(caches.match(event.request).then(function (response) {
            if (response) {
                return response
            }
            
            return fetch(event.request).then(function (response) {
                if (event.request.url.match(imgRe)) {
                    caches.open("pokeapi-js-wrapper-images-" + version).then(function (cache) {
                        // The response is opaque, if it fails cache.add() will reject it
                        cache.add(event.request.url)
                    })
                }
                return response;
            }).catch(function (error) {
                console.error(error)
            })
        }))
    }
})

self.addEventListener('install', function(event) {
    self.skipWaiting()
})
