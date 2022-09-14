function requestComplete(form, request) {
    if (request.readyState === request.DONE) {
        if (request.status === 200) {
            const contactContainerId = form.classList.contains("email-address-form") ? "email_container" : "phone_container";
            const contactContainer = document.getElementById(contactContainerId);
            contactContainer.innerHTML = request.responseText;

            userForms = contactContainer.querySelectorAll("form");

            userForms.forEach(function(form) {
                addListenersForUserForm(form);
            });
        }
    }
}

function showProgressSpinner(form) {
    const spinner = form.querySelector(".contact-spinner-container");
    const submitButton = form.querySelector("button.contact-submit-button");
    submitButton.classList.toggle("d-none");
    spinner.classList.toggle("d-none");

    spinner.parentNode.appendChild(spinner);
}

function submitContactRequest(form, deleteContact) {
    const formData = new FormData(form);
    const request = new XMLHttpRequest();
    const type = form.classList.contains("email-address-form") ? "email" : "phone";
    const requestMethod = deleteContact ? "DELETE" : "POST";

    if (type == "phone") {
        const phoneInputField = form.querySelector("input[type=tel]");
        if (phoneInputField.value) {
            const iti = window.intlTelInputGlobals.getInstance(phoneInputField);
            formData.append(phoneInputField.name, iti.getNumber());
        }
    }

    request.addEventListener("load", function(event) {
        requestComplete(form, request);
    });

    request.open(requestMethod, "user/contact/" + type);
    request.send(formData);
    showProgressSpinner(form);
}

////////////////////////////////////////////////////////////////////////////////

function addEventListenerForFormSubmit(form) {
    form.addEventListener("submit", function(event) {
        event.preventDefault();
        event.stopPropagation();

        if (form.checkValidity()) {
            const submitButton = form.querySelector("button.contact-submit-button");
            const deleteContact = submitButton.classList.contains("contact-remove-button");
            submitContactRequest(form, deleteContact);
        }

        form.classList.add('was-validated');
    }, false);
}

function addEventListenerForGetErrorsCheckbox(form) {
    getErrorsCheckbox = form.querySelector(".user-get-errors");
    getErrorsCheckbox.addEventListener("change", function(event) {
        submitContactRequest(form, false);
    });
}

function initIntlTelInput(form) {
    const phoneInputField = form.querySelector("input[type=tel]");
    const phoneInput = window.intlTelInput(phoneInputField, {
        formatOnDisplay: form.classList.contains("remove-user-contact"),
        initialCountry: "us",
        onlyCountries: ["us"],
        preferredCountries: [],
        utilsScript:
            "https://cdn.jsdelivr.net/npm/intl-tel-input@17.0.18/build/js/utils.js",
   });
}

////////////////////////////////////////////////////////////////////////////////

function addListenersForUserForm(form) {
    addEventListenerForFormSubmit(form);

    if (form.classList.contains("remove-user-contact")) {
        addEventListenerForGetErrorsCheckbox(form);
    }

    if (form.classList.contains("phone-number-form")) {
        initIntlTelInput(form);
    }
}

function addListeners() {
    const userForms = document.querySelectorAll("form");
    userForms.forEach(function(form) {
        addListenersForUserForm(form);
    });
}

addListeners();
