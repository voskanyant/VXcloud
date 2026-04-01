(function () {
  function init() {
    var toggle = document.querySelector(".admin-sidebar-toggle");
    var sidebar = document.getElementById("nav-sidebar");
    if (!toggle || !sidebar) return;

    function setOpen(opened) {
      document.body.classList.toggle("admin-sidebar-open", opened);
      toggle.setAttribute("aria-expanded", opened ? "true" : "false");
    }

    toggle.addEventListener("click", function () {
      setOpen(!document.body.classList.contains("admin-sidebar-open"));
    });

    document.addEventListener("click", function (event) {
      if (!document.body.classList.contains("admin-sidebar-open")) return;
      if (sidebar.contains(event.target) || toggle.contains(event.target)) return;
      setOpen(false);
    });

    window.addEventListener("resize", function () {
      if (window.innerWidth >= 1024) setOpen(false);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();

