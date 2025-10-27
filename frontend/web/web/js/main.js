// Script chung: menu, sidebar, navigation

document.getElementById("searchBtn").addEventListener("click", () => {
  const keyword = document.getElementById("searchInput").value.trim();
  if (keyword === "") {
    alert("Vui lòng nhập từ khóa tìm kiếm!");
    return;
  }
  alert(`Đang tìm kiếm tài liệu liên quan đến: ${keyword}`);
});

window.addEventListener("DOMContentLoaded", () => {
  const token = localStorage.getItem("token");
  const loginBtn = document.getElementById("loginBtn");
  const registerBtn = document.getElementById("registerBtn");
  const avatar = document.getElementById("userAvatar");

  if (token) {
    // Đã đăng nhập
    loginBtn.classList.add("hidden");
    registerBtn.classList.add("hidden");
    avatar.classList.remove("hidden");

    // Click avatar để đăng xuất
    avatar.addEventListener("click", () => {
      if (confirm("Bạn có muốn đăng xuất không?")) {
        localStorage.removeItem("token");
        window.location.reload();
      }
    });
  } else {
    // Chưa đăng nhập
    loginBtn.classList.remove("hidden");
    registerBtn.classList.remove("hidden");
    avatar.classList.add("hidden");
  }
});
