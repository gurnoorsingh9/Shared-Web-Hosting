(function () {

    // Generate visitor ID
    if (!localStorage.getItem("visitor_id")) {

        localStorage.setItem(
            "visitor_id",
            crypto.randomUUID()
        );
    }

    const visitorId = localStorage.getItem("visitor_id");



    // Send analytics data
    fetch("/api/track", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({

            visitor_id: visitorId,

            path: window.location.pathname,

            screen_size: `${window.screen.width}x${window.screen.height}`

        })

    });

})();