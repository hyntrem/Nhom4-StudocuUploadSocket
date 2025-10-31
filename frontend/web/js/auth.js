// Xử lý đăng nhập / đăng ký, lưu token
// ========== Xử lý Đăng nhập ==========
const loginForm = document.getElementById("loginForm");
if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();
    const msg = loginForm.querySelector(".msg");

    try {
      const res = await fetch("http://localhost:8000/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();

      if (res.ok) {
        msg.textContent = "Đăng nhập thành công!";
        msg.classList.add("success");
        localStorage.setItem("token", data.token);
        setTimeout(() => (window.location.href = "index.html"), 1000);
      } else {
        msg.textContent = data.message || "Sai email hoặc mật khẩu!";
      }
    } catch (error) {
      msg.textContent = "Không thể kết nối tới máy chủ.";
    }
  });
}

// ========== Xử lý Đăng ký ==========
const registerForm = document.getElementById("registerForm");
if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("name").value.trim();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();
    const confirmPassword = document.getElementById("confirmPassword").value.trim();
    const msg = registerForm.querySelector(".msg");

    if (password !== confirmPassword) {
      msg.textContent = "Mật khẩu không khớp!";
      return;
    }

    try {
      const res = await fetch("http://localhost:8000/api/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();

      if (res.ok) {
        msg.textContent = "Đăng ký thành công! Chuyển hướng...";
        msg.classList.add("success");
        setTimeout(() => (window.location.href = "login.html"), 1000);
      } else {
        msg.textContent = data.message || "Đăng ký thất bại!";
      }
    } catch (error) {
      msg.textContent = "Không thể kết nối tới máy chủ.";
    }
  });
}
// ========== Xử lý Đăng nhập ==========

if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value.trim();
    const msg = loginForm.querySelector(".msg");
    const popup = document.getElementById("popup");
    const popupText = document.getElementById("popupText");
    if (popup) popup.classList.add("hidden");
    popup.classList.remove("hidden");   // bật khi bắt đầu đăng nhập
    popupText.textContent = "Đang đăng nhập...";
    
    try {
      // Hiển thị popup loading
      popup.classList.remove("hidden");
      popup.classList.remove("success");
      popupText.textContent = "Đang đăng nhập...";

      const res = await fetch("http://localhost:8000/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      const data = await res.json();

      if (res.ok) {
        localStorage.setItem("token", data.token);

        // Hiển thị trạng thái thành công
        popup.classList.add("success");
        popupText.textContent = "Đăng nhập thành công!";
        setTimeout(() => {
          popup.classList.add("hidden");
          window.location.href = "index.html";
        }, 1500);
      } else {
        popup.classList.add("hidden");
        msg.textContent = data.message || "Sai email hoặc mật khẩu!";
      }
    } catch (error) {
      popup.classList.add("hidden");
      msg.textContent = "Không thể kết nối tới máy chủ.";
    }
  });
}
