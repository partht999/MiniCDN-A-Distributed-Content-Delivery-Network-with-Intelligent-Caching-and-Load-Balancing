console.log("Mini CDN client script loaded successfully!");
document.addEventListener("DOMContentLoaded", () => {
    const badge = document.getElementById("demo-badge");
    if (badge) {
        badge.innerText = "Loaded via Caching Edge Node!";
        badge.style.backgroundColor = "#6366f1";
    }
});
