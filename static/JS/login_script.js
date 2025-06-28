document.addEventListener("DOMContentLoaded", function () {
    // DOM elements
    const loginBtn = document.getElementById("login-btn");
    const signupBtn = document.getElementById("signup-btn");
    const showSignupLink = document.getElementById("show-signup");
    const showLoginLink = document.getElementById("show-login");
    const showForgotPasswordLink = document.getElementById("show-forgot-password");
    const backToLoginLink = document.getElementById("back-to-login");
    const loginForm = document.querySelector(".space-y-4:not(#signup-form)");
    const signupForm = document.getElementById("signup-form");
    const forgotPasswordForm = document.getElementById("forgot-password-form");
    const resetPasswordModal = document.getElementById("reset-password-modal");
    const sendResetLinkBtn = document.getElementById("send-reset-link-btn");
    const resetPasswordBtn = document.getElementById("reset-password-btn");
    const errorMessage = document.getElementById("error-message");
    const emailOtpModal = document.getElementById("email-otp-modal");
    const phoneOtpModal = document.getElementById("phone-otp-modal");
    const verifyEmailOtpBtn = document.getElementById("verify-email-otp-btn");
    const verifyPhoneOtpBtn = document.getElementById("verify-phone-otp-btn");

    // Toggle between login and signup forms
    showSignupLink.addEventListener("click", (e) => {
        e.preventDefault();
        loginForm.classList.add("hidden");
        signupForm.classList.remove("hidden");
        errorMessage.classList.add("hidden");
    });

    showLoginLink.addEventListener("click", (e) => {
        e.preventDefault();
        loginForm.classList.remove("hidden");
        signupForm.classList.add("hidden");
        errorMessage.classList.add("hidden");
    });

    showForgotPasswordLink.addEventListener("click", (e) => {
        e.preventDefault();
        loginForm.classList.add("hidden");
        forgotPasswordForm.classList.remove("hidden");
        errorMessage.classList.add("hidden");
    });

    backToLoginLink.addEventListener("click", (e) => {
        e.preventDefault();
        forgotPasswordForm.classList.add("hidden");
        loginForm.classList.remove("hidden");
        errorMessage.classList.add("hidden");
    });

    // Show error message
    function showError(message) {
        errorMessage.querySelector("p").textContent = message;
        errorMessage.classList.remove("hidden");
    }

    // Real-time validation for email
    document.getElementById("signup-email").addEventListener("input", function (e) {
        const email = e.target.value;
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test(email)) {
        showError("Please enter a valid email address");
        } else {
        errorMessage.classList.add("hidden");
        }
    });

    // Real-time validation for phone number
    document.getElementById("signup-phone").addEventListener("input", function (e) {
        const phone = e.target.value;
        const phoneRegex = /^[0-9]{10}$/;
        if (!phoneRegex.test(phone)) {
        showError("Please enter a valid 10-digit phone number");
        } else {
        errorMessage.classList.add("hidden");
        }
    });

    // Real-time validation for password matching
    document.getElementById("signup-confirm-password").addEventListener("input", function (e) {
        const password = document.getElementById("signup-password").value;
        const confirmPassword = e.target.value;
        if (password !== confirmPassword) {
        showError("Passwords do not match");
        } else {
        errorMessage.classList.add("hidden");
        }
    });

    // Handle login
    loginBtn.addEventListener("click", async () => {
        const email = document.getElementById("email").value.trim();
        const password = document.getElementById("password").value.trim();

        if (!email || !password) {
        showError("Please fill in all fields");
        return;
        }

        try {
        const response = await fetch("/api/login", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, password }),
        });

        const data = await response.json();
        if (response.ok) {
            window.location.href = "/";
        } else {
            showError(data.error || "Login failed");
        }
        } catch (error) {
        showError("An error occurred. Please try again.");
        }
    });

    // Handle signup
    signupBtn.addEventListener("click", async () => {
        const userName = document.getElementById("signup-user-name").value.trim();
        const email = document.getElementById("signup-email").value.trim();
        const phone = document.getElementById("signup-phone").value.trim();
        const organization = document.getElementById("signup-organization").value.trim();
        const password = document.getElementById("signup-password").value.trim();
        const confirmPassword = document.getElementById("signup-confirm-password").value.trim();

        if (!userName || !email || !phone || !password || !confirmPassword) {
        showError("Please fill in all required fields");
        return;
        }

        if (password !== confirmPassword) {
        showError("Passwords do not match");
        return;
        }

        try {
        // Send OTP to email and phone
        const otpResponse = await fetch("/api/send-otp", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, phone }),
        });

        const otpData = await otpResponse.json();
        if (otpResponse.ok) {
            // Show OTP verification modals
            emailOtpModal.classList.remove("hidden");
            phoneOtpModal.classList.remove("hidden");
        } else {
            showError(otpData.error || "Failed to send OTP");
        }
        } catch (error) {
        showError("An error occurred. Please try again.");
        }
    });

    // Handle email OTP verification
    verifyEmailOtpBtn.addEventListener("click", async () => {
        const emailOtp = document.getElementById("email-otp").value.trim();
        const email = document.getElementById("signup-email").value.trim();

        try {
        const response = await fetch("/api/verify-email-otp", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify({ email, otp: emailOtp }),
        });

        const data = await response.json();
        if (response.ok) {
            emailOtpModal.classList.add("hidden");
            alert("Email verified successfully");
        } else {
            showError(data.error || "Email OTP verification failed");
        }
        } catch (error) {
        showError("An error occurred. Please try again.");
        }
    });

    // Handle phone OTP verification
    verifyPhoneOtpBtn.addEventListener("click", async () => {
        const phoneOtp = document.getElementById("phone-otp").value.trim();
        const phone = document.getElementById("signup-phone").value.trim();

        try {
        const response = await fetch("/api/verify-phone-otp", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify({ phone, otp: phoneOtp }),
        });

        const data = await response.json();
        if (response.ok) {
            phoneOtpModal.classList.add("hidden");
            alert("Phone verified successfully");

            // Proceed with signup after OTP verification
            const userName = document.getElementById("signup-user-name").value.trim();
            const email = document.getElementById("signup-email").value.trim();
            const phone = document.getElementById("signup-phone").value.trim();
            const organization = document.getElementById("signup-organization").value.trim();
            const password = document.getElementById("signup-password").value.trim();

            const signupResponse = await fetch("/api/signup", {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
            },
            body: JSON.stringify({ userName, email, phone, organization, password }),
            });

            const signupData = await signupResponse.json();
            if (signupResponse.ok) {
            window.location.href = "/";
            } else {
            showError(signupData.error || "Signup failed");
            }
        } else {
            showError(data.error || "Phone OTP verification failed");
        }
        } catch (error) {
        showError("An error occurred. Please try again.");
        }
    });

    // Handle sending password reset link
    sendResetLinkBtn.addEventListener("click", async () => {
        const email = document.getElementById("forgot-password-email").value.trim();

        if (!email) {
        showError("Please enter your email address");
        return;
        }

        try {
        const response = await fetch("/api/forgot-password", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify({ email }),
        });

        const data = await response.json();
        if (response.ok) {
            forgotPasswordForm.classList.add("hidden");
            alert("Password reset link sent successfully");
        } else {
            showError(data.error || "Failed to send password reset link");
        }
        } catch (error) {
        showError("An error occurred. Please try again.");
        }
    });

    // Handle resetting password
    resetPasswordBtn.addEventListener("click", async () => {
        const password = document.getElementById("reset-password").value.trim();
        const confirmPassword = document.getElementById("reset-confirm-password").value.trim();

        if (!password || !confirmPassword) {
        showError("Please fill in all fields");
        return;
        }

        if (password !== confirmPassword) {
        showError("Passwords do not match");
        return;
        }

        try {
        const response = await fetch("/api/reset-password", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify({ password }),
        });

        const data = await response.json();
        if (response.ok) {
            resetPasswordModal.classList.add("hidden");
            alert("Password reset successfully");
            window.location.href = "/login";
        } else {
            showError(data.error || "Password reset failed");
        }
        } catch (error) {
        showError("An error occurred. Please try again.");
        }
    });

    // Apply theme settings from local storage
    const savedSettings = localStorage.getItem("themeSettings");
    if (savedSettings) {
        const settings = JSON.parse(savedSettings);
        if (settings.darkMode) {
        document.body.classList.add("dark-mode");
        }
        document.documentElement.style.setProperty("--primary-color", settings.primaryColor);
        applyFontSize(settings.fontSize);
    }

    function applyFontSize(size) {
        if (size === "small") {
        document.body.style.fontSize = "14px";
        } else if (size === "medium") {
        document.body.style.fontSize = "16px";
        } else if (size === "large") {
        document.body.style.fontSize = "18px";
        }
    }
});