document.addEventListener("DOMContentLoaded", function () {
// Fetch and display user name on page load
    async function fetchAndDisplayUserName() {
        try {
        const response = await fetch("/api/account-settings");
        const data = await response.json();

        if (data.user_name) {
            document.getElementById("user-name").textContent = data.user_name;
            document.getElementById("user-initials").textContent = data.user_name.substring(0, 2).toUpperCase();
        }
        } catch (error) {
        console.error("Error fetching user name:", error);
        }
    }

    fetchAndDisplayUserName();

    // DOM elements for account settings
    const accountSettingsButton = document.querySelector("button:has(.ri-user-settings-line)");
    const accountSettingsModal = document.getElementById("account-settings-modal");
    const closeAccountModalButton = document.getElementById("close-account-modal");
    const saveAccountSettingsButton = document.getElementById("save-account-settings");
    const deleteChatsButton = document.getElementById("delete-chats-btn");
    const deleteAccountButton = document.getElementById("delete-account-btn");

    // Function to open the account settings modal
    function openAccountSettingsModal() {
        accountSettingsModal.classList.remove("hidden");
        fetchUserInfo();
    }

    // Function to close the account settings modal
    function closeAccountSettingsModal() {
        accountSettingsModal.classList.add("hidden");
    }

    // Event listener for opening the account settings modal
    accountSettingsButton.addEventListener("click", openAccountSettingsModal);

    // Event listener for closing the account settings modal
    closeAccountModalButton.addEventListener("click", closeAccountSettingsModal);

    // Function to fetch and display user information
    async function fetchUserInfo() {
        try {
        const response = await fetch("/api/account-settings");
        const data = await response.json();

        document.getElementById("user-name").value = data.user_name || "";
        document.getElementById("organization-name").value = data.organization_name || "";
        document.getElementById("phone-number").value = data.phone_number || "";
        document.getElementById("email").value = data.email || "";
        } catch (error) {
        console.error("Error fetching user info:", error);
        }
    }

    // Event listener for saving account settings
    saveAccountSettingsButton.addEventListener("click", async function () {
        const formData = {
        userName: document.getElementById("user-name").value,
        organizationName: document.getElementById("organization-name").value,
        phoneNumber: document.getElementById("phone-number").value,
        email: document.getElementById("email").value,
        };

        try {
        const response = await fetch("/api/account-settings", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
            body: JSON.stringify(formData),
        });

        if (response.ok) {
            closeAccountSettingsModal();
            showSuccessMessage("Account settings updated successfully");
            document.getElementById("user-name").textContent = formData.userName;
            document.getElementById("user-initials").textContent = formData.userName.substring(0, 2).toUpperCase();
        } else {
            throw new Error("Failed to update account settings");
        }
        } catch (error) {
        console.error("Error updating account settings:", error);
        showSuccessMessage("Failed to update account settings", false);
        }
    });

    deleteChatsButton.addEventListener("click", function () {
        if (confirm("Are you sure you want to delete all chats? This action cannot be undone.")) {
        fetch("/api/chats", {
            method: "DELETE",
        })
            .then((response) => response.json())
            .then((data) => {
            window.location.href = "/";
            showSuccessMessage("All chats deleted successfully");
            })
            .catch((error) => {
            showSuccessMessage("Failed to delete chats", false);
            });
        }
    });

    // Event listener for deleting the account
    deleteAccountButton.addEventListener("click", async function () {
        if (confirm("Are you sure you want to delete your account? This action cannot be undone.")) {
            try {
                const response = await fetch("/api/account", {
                method: "DELETE",
                });

                if (response.ok) {
                    showSuccessMessage("Account deleted successfully");
                    window.location.href = "/login";
                } else {
                    throw new Error("Failed to delete account");
                }
            } catch (error) {
                console.error("Error deleting account:", error);
                showSuccessMessage("Failed to delete account", false);
            }
        }
    });

    // Add event listener for Enter key in the account settings modal
    document.getElementById("account-settings-form").addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            e.preventDefault();
            saveAccountSettingsButton.click();
        }
    });

    // Close modal when clicking outside of it
    accountSettingsModal.addEventListener("click", function (event) {
        if (event.target === accountSettingsModal) {
            closeAccountSettingsModal();
        }
    });

    // Logout functionality
    document.getElementById("logout-btn").addEventListener("click", async function () {
        try {
        const response = await fetch("/api/logout", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
        });

        if (response.ok) {
            window.location.href = "/login";
        } else {
            throw new Error("Logout failed");
        }
        } catch (error) {
        console.error("Error during logout:", error);
        showSuccessMessage("Failed to logout", false);
        }
    });
});

document.addEventListener("DOMContentLoaded", function () {
    // Global variables
    let currentChatId = null;
    let currentUserId = null;
    let chats = {};
    let activeDropdown = null;
    let currentThemeSettings = {
        darkMode: false,
        primaryColor: "#87CEEB",
        fontSize: "medium",
    };

    // DOM elements
    const dragArea = document.querySelector(".drag-area");
    const uploadBtn = document.querySelector(".upload-btn");
    const documentPanel = document.querySelector(".document-panel");
    const documentList = document.getElementById("document-list");
    const chatMessages = document.getElementById("chat-messages");
    const newChatBtn = document.getElementById("new-chat-btn");
    const chatTabs = document.getElementById("chat-tabs");
    const chatInput = document.getElementById("chat-input");
    const sendBtn = document.getElementById("send-btn");
    const body = document.body;

    // Load theme settings from local storage
    function loadThemeSettings() {
        const savedSettings = localStorage.getItem("themeSettings");
        if (savedSettings) {
        currentThemeSettings = JSON.parse(savedSettings);
        applyThemeSettings(currentThemeSettings);
        }
    }

    // Save theme settings to local storage
    function saveThemeSettings(settings) {
        localStorage.setItem("themeSettings", JSON.stringify(settings));
    }

    // Initialize the application
    async function init() {
        loadThemeSettings();

        // Check if we have a user ID in session storage
        currentUserId = sessionStorage.getItem("user_id");
        if (!currentUserId) {
        // If not, create a new one and store it
        const response = await fetch("/api/chats", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
        });
        const data = await response.json();
        currentUserId = data.user_id;
        sessionStorage.setItem("user_id", currentUserId);
        }

        // Load chats for this user
        await loadChats();

        // If there are no chats, create a new one
        if (Object.keys(chats).length === 0) {
        await createNewChat();
        } else {
        // Otherwise, load the most recent chat
        const chatIds = Object.keys(chats);
        chatIds.sort(
            (a, b) => new Date(chats[b].created_at) - new Date(chats[a].created_at)
        );
        await switchToChat(chatIds[0]);
        }
    }

    // Load all chats for the current user
    async function loadChats() {
        try {
        const response = await fetch("/api/chats");
        const data = await response.json();

        // Clear existing chats
        chats = {};

        // Add each chat to our chats object
        data.forEach((chat) => {
            chats[chat.id] = {
            title: chat.title,
            created_at: chat.created_at,
            messages: [],
            documents: [],
            };
        });

        // Update the chat tabs UI
        updateChatTabs();
        } catch (error) {
        console.error("Error loading chats:", error);
        }
    }

    // Create a new chat
    async function createNewChat() {
        try {
        const response = await fetch("/api/chats", {
            method: "POST",
            headers: {
            "Content-Type": "application/json",
            },
        });
        const data = await response.json();

        // Add the new chat to our chats object
        chats[data.id] = {
            title: data.title,
            created_at: data.created_at,
            messages: [],
            documents: [],
        };

        // Switch to the new chat
        await switchToChat(data.id);
        } catch (error) {
        console.error("Error creating new chat:", error);
        }
    }

    // Switch to a specific chat
    async function switchToChat(chatId) {
        currentChatId = chatId;

        // Update the active chat tab
        updateChatTabs();

        // Clear the current messages
        chatMessages.innerHTML = "";

        // Load messages for this chat
        await loadMessages(chatId);

        // Load documents for this chat
        await loadDocuments(chatId);

        // Scroll to the bottom of the chat
        chatMessages.scrollTop = chatMessages.scrollHeight;

        // Focus the input
        chatInput.focus();
    }

    // Load messages for a specific chat
    async function loadMessages(chatId) {
        try {
        const response = await fetch(`/api/chats/${chatId}/messages`);
        const messages = await response.json();

        // Clear existing messages
        chats[chatId].messages = [];

        // Add each message to the chat
        messages.forEach((message) => {
            if (message.sender === "user") {
            addUserMessage(message.content, false);
            } else {
            addBotMessage(message.content, false);
            }
        });
        } catch (error) {
        console.error("Error loading messages:", error);
        }
    }

    // Load documents for a specific chat
    async function loadDocuments(chatId) {
        try {
        const response = await fetch(`/api/documents?chat_id=${chatId}`);
        const documents = await response.json();

        // Clear existing documents
        documentList.innerHTML = "";
        chats[chatId].documents = [];

        // Add each document to the document list
        documents.forEach((doc) => {
            addDocumentToList(doc);
            chats[chatId].documents.push(doc);
        });
        } catch (error) {
        console.error("Error loading documents:", error);
        }
    }

    // Update the chat tabs UI
    function updateChatTabs() {
        // Clear existing tabs
        chatTabs.innerHTML = "";

        // Add a tab for each chat
        Object.entries(chats).forEach(([chatId, chat]) => {
        const tab = document.createElement("button");
        tab.className = `px-4 py-2 rounded-full text-sm whitespace-nowrap flex items-center ${
            chatId === currentChatId
            ? "bg-primary text-white"
            : "bg-gray-100 text-gray-600"
        }`;
        tab.innerHTML = `
            <span>${chat.title}</span>
            <div class="w-5 h-5 flex items-center justify-center ml-2">
            <i class="ri-close-line"></i>
            </div>
        `;
        tab.addEventListener("click", (e) => {
            if (e.target.closest(".ri-close-line")) {
                deleteChat(chatId);
            } else {
                switchToChat(chatId);
            }
        });
        chatTabs.appendChild(tab);
        });
    }

    // Delete a chat
    async function deleteChat(chatId) {
        if (Object.keys(chats).length <= 1) {
        showSuccessMessage("You must have at least one chat", false);
        return;
        }

        try {
            const response = await fetch(`/api/chats/${chatId}`, {
                method: "DELETE",
            });

            if (response.ok) {
                // Remove the chat from our chats object
                delete chats[chatId];

                // If we deleted the current chat, switch to another one
                if (chatId === currentChatId) {
                    const remainingChatIds = Object.keys(chats);
                    await switchToChat(remainingChatIds[0]);
                } else {
                    // Otherwise just update the UI
                    updateChatTabs();
                }

                showSuccessMessage("Chat deleted successfully");
            } else {
                throw new Error("Failed to delete chat");
            }
        } catch (error) {
            console.error("Error deleting chat:", error);
            showSuccessMessage("Failed to delete chat", false);
        }
    }

    // Function to create dropdown menu for document items
    function createDropdownMenu(docId) {
        const dropdown = document.createElement("div");
        dropdown.className = "document-item-dropdown absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg z-50 py-2 border border-gray-100";
        dropdown.innerHTML = `
        <button class="w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center download-btn" data-id="${docId}">
            <div class="w-5 h-5 flex items-center justify-center mr-2">
            <i class="ri-download-line"></i>
            </div>
            Download
        </button>
        <button class="w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center preview-btn" data-id="${docId}">
            <div class="w-5 h-5 flex items-center justify-center mr-2">
            <i class="ri-eye-line"></i>
            </div>
            Preview
        </button>
        <button class="w-full px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 flex items-center rename-btn" data-id="${docId}">
            <div class="w-5 h-5 flex items-center justify-center mr-2">
            <i class="ri-edit-line"></i>
            </div>
            Rename
        </button>
        <hr class="my-2 border-gray-100">
        <button class="w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50 flex items-center delete-btn" data-id="${docId}">
            <div class="w-5 h-5 flex items-center justify-center mr-2">
            <i class="ri-delete-bin-line"></i>
            </div>
            Delete
        </button>
        `;
        return dropdown;
    }

    // Function to hide dropdown
    function hideDropdown() {
        if (activeDropdown) {
        activeDropdown.remove();
        activeDropdown = null;
        }
    }

    // Event listener for document item actions
    document.addEventListener("click", async (e) => {
        // Handle document dropdown
        const moreButton = e.target.closest(".document-item .ri-more-2-fill");
        if (moreButton) {
        e.stopPropagation();
        hideDropdown();

        const documentItem = moreButton.closest(".document-item");
        const docId = documentItem.dataset.id;

        // Create and position the dropdown
        const dropdown = createDropdownMenu(docId);
        const rect = documentItem.getBoundingClientRect();
        dropdown.style.position = "fixed";
        dropdown.style.top = `${rect.top + window.scrollY}px`;
        dropdown.style.left = `${rect.right + window.scrollX}px`;
        document.body.appendChild(dropdown);
        activeDropdown = dropdown;
        return;
        }

        // Handle download button
        const downloadBtn = e.target.closest(".download-btn");
        if (downloadBtn) {
            const docId = downloadBtn.dataset.id;
            const docName = document.querySelector(`.document-item[data-id="${docId}"] h4`).textContent;

            showSuccessMessage(`Downloading ${docName}`);

            try {
                const response = await fetch(`/api/documents/${docId}`);
                if (response.ok) {
                    const blob = await response.blob();
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement("a");
                    a.href = url;
                    a.download = docName;
                    document.body.appendChild(a);
                    a.click();
                    document.body.removeChild(a);
                    window.URL.revokeObjectURL(url);
                } else {
                    throw new Error("Failed to download document");
                }
            } catch (error) {
                console.error("Error downloading document:", error);
                showSuccessMessage("Failed to download document", false);
            }
            return;
        }

        // Handle preview button
        const previewBtn = e.target.closest(".preview-btn");
        if (previewBtn) {
            const docId = previewBtn.dataset.id;
            previewDocument(docId);
            return;
        }

        // Handle delete button
        const deleteBtn = e.target.closest(".delete-btn");
        if (deleteBtn) {
            showLoader("Deleting document...");
            const docId = deleteBtn.dataset.id;
            try {
                const response = await fetch(`/api/documents/${docId}`, {
                    method: "DELETE",
                });

                if (response.ok) {
                    const docElement = document.querySelector(`.document-item[data-id="${docId}"]`);
                    if (docElement) {
                        docElement.remove();
                    }

                    if (currentChatId && chats[currentChatId]) {
                        chats[currentChatId].documents = chats[currentChatId].documents.filter((doc) => doc.id !== docId);
                    }

                    showSuccessMessage("Document deleted successfully");
                } else {
                throw new Error("Failed to delete document");
                }
            } catch (error) {
                console.error("Error deleting document:", error);
                showSuccessMessage("Failed to delete document", false);
            } finally {
                hideLoader();
            }
            return;
        }

        // Handle rename button
        const renameBtn = e.target.closest(".rename-btn");
        if (renameBtn) {
            const docId = renameBtn.dataset.id;
            const docElement = document.querySelector(`.document-item[data-id="${docId}"]`);
            const currentName = docElement.querySelector("h4").textContent;
            const newName = prompt("Enter new name for the document:", currentName);

            if (newName && newName !== currentName) {
                docElement.querySelector("h4").textContent = newName;
                showSuccessMessage(`Document renamed to ${newName}`);
            }
            return;
        }

        // Hide dropdown if clicking elsewhere
        hideDropdown();
    });

    // Drag & Drop functionality
    ["dragenter", "dragover", "dragleave", "drop"].forEach((eventName) => {
        dragArea.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    ["dragenter", "dragover"].forEach((eventName) => {
        dragArea.addEventListener(eventName, highlight, false);
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dragArea.addEventListener(eventName, unhighlight, false);
    });

    function highlight() {
        dragArea.classList.add("active");
    }

    function unhighlight() {
        dragArea.classList.remove("active");
    }

    dragArea.addEventListener("drop", handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;
        handleFiles(files);
    }

    // Show loader function
    function showLoader(message = "Processing...") {
        const loader = document.getElementById('loading-indicator');
        loader.style.display = 'flex';
        loader.querySelector('p').textContent = message;
    }

    // Hide loader function
    function hideLoader() {
        document.getElementById('loading-indicator').style.display = 'none';
    }

    // Handle file uploads
    async function handleFiles(files) {
        if (!currentChatId) {
            showSuccessMessage("Please create or select a chat first", false);
            return;
        }

        if (files.length > 0) {
            const file = files[0];
            showLoader("Uploading document...");

            try {
                const formData = new FormData();
                formData.append("file", file);
                formData.append("chat_id", currentChatId);

                const response = await fetch("/api/upload", {
                    method: "POST",
                    body: formData,
                });

                if (response.ok) {
                    const data = await response.json();
                    addDocumentToList(data);
                    showSuccessMessage("Document uploaded successfully");
                    if (!chats[currentChatId].documents) {
                        chats[currentChatId].documents = [];
                    }
                    chats[currentChatId].documents.push(data);
                } else {
                    const errorData = await response.json();
                    throw new Error(errorData.error || "Failed to upload document");
                }
            } catch (error) {
                console.error("Upload error:", error);
                showSuccessMessage(error.message || "Failed to upload document", false);
            } finally {
                hideLoader();
            }
        }
    }

    // Add a document to the document list
    function addDocumentToList(doc) {
        let iconClass = "ri-file-text-line";
        let bgClass = "bg-blue-100";
        let textClass = "text-blue-500";

        if (doc.extension === "pdf") {
            iconClass = "ri-file-pdf-line";
            bgClass = "bg-red-100";
            textClass = "text-red-500";
        } else if (["doc", "docx"].includes(doc.extension)) {
            iconClass = "ri-file-word-line";
            bgClass = "bg-purple-100";
            textClass = "text-purple-500";
        } else if (["xls", "xlsx"].includes(doc.extension)) {
            iconClass = "ri-file-excel-line";
            bgClass = "bg-green-100";
            textClass = "text-green-500";
        }

        const newDocumentItem = document.createElement("div");
        newDocumentItem.className = "document-item p-3 rounded flex items-start cursor-pointer relative";
        newDocumentItem.dataset.id = doc.id;
        newDocumentItem.innerHTML = `
        <div class="w-8 h-8 flex items-center justify-center ${bgClass} rounded mr-3">
            <i class="${iconClass} ${textClass}"></i>
        </div>
        <div class="flex-1">
            <h4 class="text-sm font-medium text-gray-800">${doc.filename}</h4>
            <p class="text-xs text-gray-500">Uploaded ${doc.upload_date} • ${doc.size}</p>
        </div>
        <div class="w-8 h-8 flex items-center justify-center text-gray-400 hover:text-gray-600">
            <i class="ri-more-2-fill"></i>
        </div>`;
        documentList.insertBefore(newDocumentItem, documentList.firstChild);
        documentList.scrollTop = 0;
    }

    // Show a success/error message
    function showSuccessMessage(message, success = true) {
        const successMessage = document.createElement("div");
        successMessage.className = `fixed top-4 right-4 ${
        success ? "bg-green-50 border-l-4 border-green-400" : "bg-red-50 border-l-4 border-red-400"
        } p-4 rounded shadow-md transform transition-transform duration-300 ease-in-out z-50`;
        successMessage.style.transform = "translateX(100%)";
        successMessage.innerHTML = `
        <div class="flex">
            <div class="flex-shrink-0">
            <div class="w-5 h-5 flex items-center justify-center ${
                success ? "text-green-400" : "text-red-400"
            }">
                <i class="ri-${success ? "check" : "close"}-line"></i>
            </div>
            </div>
            <div class="ml-3">
            <p class="text-sm ${
                success ? "text-green-700" : "text-red-700"
            }">${message}</p>
            </div>
        </div>
        `;
        document.body.appendChild(successMessage);
        setTimeout(() => {
            successMessage.style.transform = "translateX(0)";
        }, 100);
        setTimeout(() => {
            successMessage.style.transform = "translateX(100%)";
            successMessage.style.opacity = "0";
            setTimeout(() => {
                document.body.removeChild(successMessage);
            }, 300);
        }, 3000);
    }

    // Click to upload
    dragArea.addEventListener("click", () => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".pdf,.doc,.docx,.txt,.xls,.xlsx";
        input.onchange = (e) => {
            const files = e.target.files;
            handleFiles(files);
        };
        input.click();
    });

    uploadBtn.addEventListener("click", () => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".pdf,.doc,.docx,.txt,.xls,.xlsx";
        input.onchange = (e) => {
            const files = e.target.files;
            handleFiles(files);
        };
        input.click();
    });

    // Add a user message to the chat
    function addUserMessage(message, saveToDb = true) {
        const userInitials = document.getElementById("user-initials").textContent;
        const messageElement = document.createElement("div");
        messageElement.className = "flex items-start self-end max-w-[80%]";
        messageElement.innerHTML = `
        <div class="user-message p-4 rounded-lg">
            <p class="text-gray-800">${message}</p>
        </div>
        <div class="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center ml-3">
            <span class="text-sm font-medium text-gray-600">${userInitials}</span>
        </div>
        `;
        chatMessages.appendChild(messageElement);

        if (currentChatId && chats[currentChatId]) {
            chats[currentChatId].messages.push({
                type: "user",
                content: message,
                element: messageElement,
            });
        }

        chatMessages.scrollTop = chatMessages.scrollHeight;

        if (saveToDb && currentChatId) {
            sendMessageToServer(message);
        }
    }

    // Add a bot message to the chat
    function addBotMessage(message, saveToDb = true) {
        const messageElement = document.createElement("div");
        messageElement.className = "flex items-start max-w-[80%]";
        messageElement.innerHTML = `
        <div class="w-8 h-8 bg-primary rounded-full flex items-center justify-center text-white mr-3">
            <div class="w-8 h-8 flex items-center justify-center">
            <i class="ri-robot-line"></i>
            </div>
        </div>
        <div class="bot-message p-4 rounded-lg">
            <p class="text-gray-800">${message}</p>
        </div>`;
        chatMessages.appendChild(messageElement);

        if (currentChatId && chats[currentChatId]) {
            chats[currentChatId].messages.push({
                type: "bot",
                content: message,
                element: messageElement,
            });
        }
        chatMessages.scrollTop = chatMessages.scrollHeight;
    }

    // Add a typing indicator to the chat
    function addTypingIndicator() {
        const typingElement = document.createElement("div");
        typingElement.className = "flex items-start max-w-[80%] typing-indicator-container";
        typingElement.innerHTML = `
        <div class="w-8 h-8 bg-primary rounded-full flex items-center justify-center text-white mr-3">
            <div class="w-8 h-8 flex items-center justify-center">
            <i class="ri-robot-line"></i>
            </div>
        </div>
        <div class="flex items-center bot-message p-3 rounded-lg">
            <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
            </div>
            <span class="ml-2 text-gray-600">Gathering information...</span>
        </div>
        `;
        chatMessages.appendChild(typingElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return typingElement;
    }

    // Remove a typing indicator from the chat
    function removeTypingIndicator(element) {
        if (element && element.parentNode === chatMessages) {
            chatMessages.removeChild(element);
        }
    }

    // Send a message to the server
    async function sendMessageToServer(message) {
        try {
            const typingIndicator = addTypingIndicator();

            const response = await fetch(`/api/chats/${currentChatId}/messages`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                },
                body: JSON.stringify({ content: message }),
            });
            if (response.ok) {
                const data = await response.json();
                removeTypingIndicator(typingIndicator);
                addBotMessage(data.bot_response.content); // Changed from data.reply to data.bot_response.content
            } else {
                throw new Error("Failed to send message");
            }
        } catch (error) {
            console.error("Error sending message:", error);
            removeTypingIndicator(typingIndicator);
            showSuccessMessage("Failed to send message", false);
        }
    }

    // Send a message when the send button is clicked
    sendBtn.addEventListener("click", () => {
        const message = chatInput.value.trim();
        if (message) {
            addUserMessage(message);
            chatInput.value = "";
        }
    });

    // Send a message when Enter is pressed
    chatInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
            const message = chatInput.value.trim();
            if (message) {
                addUserMessage(message);
                chatInput.value = "";
            }
        }
    });

    // Create a new chat when the new chat button is clicked
    newChatBtn.addEventListener("click", createNewChat);

    // Function to preview document
    async function previewDocument(docId) {
        try {
            const response = await fetch(`/api/documents/${docId}`);
            if (response.ok) {
                const blob = await response.blob();
                const url = window.URL.createObjectURL(blob);

                const previewModal = document.getElementById("preview-modal");
                const documentContent = document.getElementById("document-content");
                documentContent.innerHTML = `<iframe src="${url}" style="width:100%; height:500px;" frameborder="0"></iframe>`;
                previewModal.classList.remove("hidden");
            } else {
                throw new Error("Failed to fetch document");
            }
        } catch (error) {
        console.error("Error previewing document:", error);
        showSuccessMessage("Failed to preview document", false);
        }
    }

    // Event listener to close the preview modal
    document.getElementById("close-preview-modal").addEventListener("click", function () {
        document.getElementById("preview-modal").classList.add("hidden");
    });

    // Initialize the application
    init();

    // Settings dropdown handler
    const settingsButton = document.getElementById("settings-button");
    const settingsDropdown = document.getElementById("settings-dropdown");
    const themeSettingsButton = settingsDropdown.querySelector("button:has(.ri-palette-line)");

    function toggleDropdown() {
        settingsDropdown.classList.toggle("hidden");
    }

    function hideSettingsDropdown(e) {
        if (!document.getElementById("settings-container").contains(e.target)) {
            settingsDropdown.classList.add("hidden");
        }
    }

    function createThemeModal() {
        const modal = document.createElement("div");
        modal.id = "theme-settings-modal";
        modal.className = "fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50";
        modal.innerHTML = `
        <div class="bg-white rounded-lg w-[480px] shadow-xl">
            <div class="p-6 border-b border-gray-100">
            <div class="flex items-center justify-between">
                <h3 class="text-xl font-semibold text-gray-800">Theme Settings</h3>
                <button id="close-theme-modal" class="text-gray-400 hover:text-gray-600">
                <div class="w-6 h-6 flex items-center justify-center">
                    <i class="ri-close-line"></i>
                </div>
                </button>
            </div>
            </div>
            <div class="p-6">
            <div class="space-y-6">
                <div>
                <label class="flex items-center justify-between mb-4">
                    <span class="text-sm font-medium text-gray-700">Dark Mode</span>
                    <div class="relative inline-block w-12 h-6 transition duration-200 ease-in-out">
                    <input type="checkbox" id="theme-mode-toggle" class="opacity-0 absolute w-full h-full cursor-pointer z-10" ${
                        currentThemeSettings.darkMode ? "checked" : ""
                    }>
                    <div class="w-12 h-6 ${
                        currentThemeSettings.darkMode ? "bg-primary" : "bg-gray-200"
                    } rounded-full absolute top-0 left-0"></div>
                    <div class="w-6 h-6 bg-white rounded-full absolute top-0 left-0 transform scale-90 shadow transition duration-200 ${
                        currentThemeSettings.darkMode ? "translate-x-6" : ""
                    }"></div>
                    </div>
                </label>
                </div>
                <div>
                <label class="block text-sm font-medium text-gray-700 mb-4">Font Size</label>
                <div class="flex items-center space-x-4">
                    <button class="px-4 py-2 text-sm bg-gray-100 rounded-full text-gray-600 font-size-option ${
                    currentThemeSettings.fontSize === "small" ? "border-2 border-primary" : ""
                    }" data-size="small">Small</button>
                    <button class="px-4 py-2 text-sm bg-gray-100 rounded-full text-gray-600 font-size-option ${
                    currentThemeSettings.fontSize === "medium" ? "border-2 border-primary" : ""
                    }" data-size="medium">Medium</button>
                    <button class="px-4 py-2 text-sm bg-gray-100 rounded-full text-gray-600 font-size-option ${
                    currentThemeSettings.fontSize === "large" ? "border-2 border-primary" : ""
                    }" data-size="large">Large</button>
                </div>
                </div>
                <div>
                <label class="block text-sm font-medium text-gray-700 mb-4">Preview</label>
                <div class="p-4 border border-gray-200 rounded-lg space-y-4">
                    <div class="flex items-start max-w-[80%]">
                    <div class="w-8 h-8 bg-primary rounded-full flex items-center justify-center text-white mr-3">
                        <div class="w-8 h-8 flex items-center justify-center">
                        <i class="ri-robot-line"></i>
                        </div>
                    </div>
                    <div class="bot-message p-4 rounded-lg">
                        <p class="text-gray-800">This is how your chat messages will look.</p>
                    </div>
                    </div>
                    <div class="flex items-start self-end max-w-[80%] justify-end w-full">
                    <div class="user-message p-4 rounded-lg">
                        <p class="text-gray-800">Preview of user messages</p>
                    </div>
                    <div class="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center ml-3">
                        <span class="text-sm font-medium text-gray-600">U</span>
                    </div>
                    </div>
                </div>
                </div>
            </div>
            </div>
            <div class="p-6 border-t border-gray-100 flex justify-end space-x-4">
            <button id="cancel-theme-settings" class="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 !rounded-button whitespace-nowrap">Cancel</button>
            <button id="apply-theme-settings" class="px-4 py-2 text-sm bg-primary text-white !rounded-button whitespace-nowrap">Apply Changes</button>
            </div>
        </div>
        `;
        document.body.appendChild(modal);
        setupThemeModalHandlers(modal);
    }

    function setupThemeModalHandlers(modal) {
        const closeBtn = modal.querySelector("#close-theme-modal");
        const cancelBtn = modal.querySelector("#cancel-theme-settings");
        const applyBtn = modal.querySelector("#apply-theme-settings");
        const themeToggle = modal.querySelector("#theme-mode-toggle");
        const fontSizeButtons = modal.querySelectorAll(".font-size-option");

        function closeModal() {
            modal.remove();
        }

        closeBtn.addEventListener("click", closeModal);
        cancelBtn.addEventListener("click", closeModal);
        modal.addEventListener("click", (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });

        themeToggle.addEventListener("change", function () {
            const toggleBg = this.nextElementSibling;
            const toggleCircle = toggleBg.nextElementSibling;
            if (this.checked) {
                toggleBg.classList.remove("bg-gray-200");
                toggleBg.classList.add("bg-primary");
                toggleCircle.classList.add("translate-x-6");
                body.classList.add("dark-mode");
                currentThemeSettings.darkMode = true;
            } else {
                toggleBg.classList.add("bg-gray-200");
                toggleBg.classList.remove("bg-primary");
                toggleCircle.classList.remove("translate-x-6");
                body.classList.remove("dark-mode");
                currentThemeSettings.darkMode = false;
            }
        });

        fontSizeButtons.forEach((button) => {
            button.addEventListener("click", () => {
                fontSizeButtons.forEach((btn) => {
                btn.classList.remove("border-2", "border-primary");
                });
                button.classList.add("border-2", "border-primary");
                const fontSize = button.dataset.size;
                applyFontSize(fontSize);
                currentThemeSettings.fontSize = fontSize;
            });
        });

        applyBtn.addEventListener("click", () => {
            saveThemeSettings(currentThemeSettings);
            const successMessage = document.createElement("div");
            successMessage.className = "fixed top-4 right-4 bg-green-50 border-l-4 border-green-400 p-4 rounded shadow-md transform transition-transform duration-300 ease-in-out z-50";
            successMessage.style.transform = "translateX(100%)";
            successMessage.innerHTML = `
                <div class="flex">
                <div class="flex-shrink-0">
                    <div class="w-5 h-5 flex items-center justify-center text-green-400">
                    <i class="ri-check-line"></i>
                    </div>
                </div>
                <div class="ml-3">
                    <p class="text-sm text-green-700">Theme settings updated successfully</p>
                </div>
                </div>`;
            document.body.appendChild(successMessage);
            setTimeout(() => {
                successMessage.style.transform = "translateX(0)";
            }, 100);
            setTimeout(() => {
                successMessage.style.transform = "translateX(100%)";
                successMessage.style.opacity = "0";
                setTimeout(() => {
                    document.body.removeChild(successMessage);
                }, 300);
            }, 3000);
            closeModal();
        });
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

    function applyThemeSettings(settings) {
        if (settings.darkMode) {
            body.classList.add("dark-mode");
        } else {
            body.classList.remove("dark-mode");
        }
        document.documentElement.style.setProperty("--primary-color", settings.primaryColor);
        applyFontSize(settings.fontSize);
    }

    themeSettingsButton.addEventListener("click", () => {
        settingsDropdown.classList.add("hidden");
        createThemeModal();
    });

    settingsButton.addEventListener("click", toggleDropdown);
    document.addEventListener("click", hideSettingsDropdown);
});

document.addEventListener("DOMContentLoaded", function () {
fetch('/api/check-auth')
    .then(response => {
        if (!response.ok) {
            // Redirect to login page if not authenticated
            window.location.href = '/login';
        }
    })
    .catch(error => {
        console.error('Error checking authentication:', error);
        window.location.href = '/login';
    });
});