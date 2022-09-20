var newCriteriaIndex = document.querySelectorAll(".criteria-row").length;

function replaceAttributesWithCurrentIndex(row) {
    allElements = row.querySelectorAll("*");

    const templatePrefix = "important_criteria-0-"
    const criteriaPrefix = "important_criteria-" + newCriteriaIndex + "-";
    allElements.forEach(function(element) {
        if (element.id) {
            element.id = element.id.replace(templatePrefix, criteriaPrefix);
        }
        if (element.name) {
            element.name = element.name.replace(templatePrefix, criteriaPrefix);
        }
        if (element.hasAttribute("for")) {
            element.setAttribute("for", element.getAttribute("for").replace(templatePrefix, criteriaPrefix));
        }
        if (element.hasAttribute("data-bs-target")) {
            element.setAttribute("data-bs-target", element.getAttribute("data-bs-target").replace(templatePrefix, criteriaPrefix));
        }
        if (element.hasAttribute("aria-controls")) {
            element.setAttribute("aria-controls", element.getAttribute("aria-controls").replace(templatePrefix, criteriaPrefix));
        }
        if (element.hasAttribute("value")) {
            element.setAttribute("value", element.getAttribute("value").replace(templatePrefix, criteriaPrefix));
        }
    });

    newCriteriaIndex++;
}

function addCriteria() {
    const template = document.getElementById("template_form_row");
    const criteriaRowFragment = template.content.cloneNode(true);
    const destination = document.getElementById("criteriaRows");

    const criteriaRow = criteriaRowFragment.querySelector(".criteria-row");
    replaceAttributesWithCurrentIndex(criteriaRow);
    addListenersForCriteria(criteriaRow);

    destination.appendChild(criteriaRowFragment);
    destination.lastElementChild.scrollIntoView();
}

function checkDateRequirements(row) {
    const specialType = row.querySelector("[id$=\"special_type\"]");
    const checkIn = row.querySelector("[id$=\"check_in_date\"]");
    const checkOut = row.querySelector("[id$=\"check_out_date\"]");

    checkOut.required = Boolean(checkIn.value);
    checkIn.required = specialType.value == "{{ SpecialTypes.PRECONFIRM }}" && Boolean(checkOut.value);
}

function eraseFields(fields) {
    fields.forEach(function(field) {
        field.querySelectorAll("input[type=date],input[type=number]").forEach(function(input) {
            input.value = "";
        });

        field.querySelectorAll("input[type=checkbox]").forEach(function(input) {
            input.checked = false;
            input.indeterminate = false;
        });
    });
}

function showPreconfirmFields(show, row) {
    const preconfirmFields = row.querySelectorAll(".disc-points-hidden");
    const discPointFields = row.querySelectorAll(".preconfirm-hidden");

    preconfirmFields.forEach(function(preconfirm) {
        preconfirm.hidden = !show;
    });
    discPointFields.forEach(function(discPoint) {
        discPoint.hidden = show;
    });

    const fieldsToErase = show ? discPointFields : preconfirmFields;
    eraseFields(fieldsToErase);
}

function updateCategoryCheckbox(categoryCheckbox, childrenCheckboxes) {
    var checkedCount = 0;
    childrenCheckboxes.forEach(function(checkbox) {
        if (checkbox.checked) {
            checkedCount++;
        }
    });

    categoryCheckbox.checked = checkedCount === childrenCheckboxes.length;
    categoryCheckbox.indeterminate = !categoryCheckbox.checked && checkedCount > 0;
}

////////////////////////////////////////////////////////////////////////////////

function addEventListenerForDates(row) {
    const checkIn = row.querySelector("[id$=\"check_in_date\"]");
    const checkOut = row.querySelector("[id$=\"check_out_date\"]");

    checkIn.addEventListener("change", function(event) {
        checkDateRequirements(row);
    });

    checkOut.addEventListener("change", function(event) {
        checkDateRequirements(row);
    });
}

function addEventListenerForCriteriaTypeChange(row) {
    const criteriaType = row.querySelector("[id$=\"special_type\"]");
    criteriaType.addEventListener("change", function(event) {
        isPreconfirm = criteriaType.value == "preconfirm";
        showPreconfirmFields(isPreconfirm, row);
        checkDateRequirements(row);
    });
}

function addEventListenerForRemoveButton(row) {
    const button = row.querySelector(".remove-criteria-button");
    button.addEventListener("click", function(event) {
        row.classList.remove("show");
    });
    row.addEventListener("transitionend", function(event) {
        if (event.target === row) {
            row.remove();
        }
    });
}

function addEventListenersForCharacteristicCheckboxes(row) {
    const categoryCheckboxes = row.querySelectorAll(".select-all-input");
    categoryCheckboxes.forEach(function(checkbox) {
        const childrenCheckboxes = row.querySelectorAll("#" + checkbox.value + " input[type=checkbox]");

        checkbox.addEventListener("change", function(event) {
            childrenCheckboxes.forEach(function(childCheckbox) {
                childCheckbox.checked = checkbox.checked;
            });
        });

        childrenCheckboxes.forEach(function(childCheckbox) {
            childCheckbox.addEventListener("change", function(event) {
                updateCategoryCheckbox(checkbox, childrenCheckboxes);
            });
        });

        updateCategoryCheckbox(checkbox, childrenCheckboxes);
    });


}

function addEventListenerForAddButton() {
    const addCriteriaButton = document.getElementById("add_criteria_button");
    addCriteriaButton.addEventListener("click", function(event) {
        addCriteria();
        addCriteriaButton.blur();
    });
}

function addEventListenerForFormSubmit() {
    const criteriaForm = document.getElementById("criteria_form");
    criteriaForm.addEventListener('submit', function (event) {
        if (!criteriaForm.checkValidity()) {
            event.preventDefault()
            event.stopPropagation()

            invalidField = criteriaForm.querySelector("input.form-control:invalid");
            invalidField.scrollIntoView();
        }

        criteriaForm.classList.add('was-validated')
    }, false)
}

////////////////////////////////////////////////////////////////////////////////

function addListenersForCriteria(row) {
    addEventListenerForDates(row);
    addEventListenerForCriteriaTypeChange(row);
    addEventListenerForRemoveButton(row);
    addEventListenersForCharacteristicCheckboxes(row);
}

function addListeners() {
    addEventListenerForAddButton();
    addEventListenerForFormSubmit();

    const rows = document.querySelectorAll(".criteria-row");
    rows.forEach(function(row) {
        addListenersForCriteria(row);
    });
}

addListeners();
