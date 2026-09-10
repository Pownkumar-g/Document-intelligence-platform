/**
 * Document Intelligence Platform – Frontend JS
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('uploadForm');
    if (form) {
        form.addEventListener('submit', handleUpload);
    }
});

async function handleUpload(event) {
    event.preventDefault();

    const fileInput = document.getElementById('fileInput');
    const docType = document.getElementById('documentType');
    const statusDiv = document.getElementById('uploadStatus');
    const progressBar = document.getElementById('progressBar');
    const processBtn = document.getElementById('processBtn');

    // Validate inputs
    if (!fileInput.files.length) {
        showStatus(statusDiv, 'Please select a file.', 'error');
        return;
    }
    if (!docType.value) {
        showStatus(statusDiv, 'Please select a document type.', 'error');
        return;
    }

    // Validate file extension
    const fileName = fileInput.files[0].name.toLowerCase();
    const validExtensions = ['.pdf', '.jpg', '.jpeg', '.png'];
    const hasValidExt = validExtensions.some(ext => fileName.endsWith(ext));
    if (!hasValidExt) {
        showStatus(statusDiv, 'Only PDF / JPG / PNG files are supported.', 'error');
        return;
    }

    // Prepare form data
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    formData.append('document_type', docType.value);

    // UI feedback
    processBtn.disabled = true;
    processBtn.textContent = '⏳ Processing...';
    progressBar.style.display = 'block';
    showStatus(statusDiv, 'Uploading and processing document... This may take 10-30 seconds.', 'loading');

    try {
        const response = await fetch('/api/v1/documents/process', {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();

        if (response.ok) {
            showStatus(
                statusDiv,
                `✅ Document processed successfully! Status: ${result.processing_status}`,
                'success'
            );
            // Redirect to result page after a short delay
            setTimeout(() => {
                window.location.href = `/document/${encodeURIComponent(result.document_name)}`;
            }, 1000);
        } else {
            const errorMsg = result.detail?.error?.message || result.detail || 'Processing failed.';
            showStatus(statusDiv, `❌ Error: ${errorMsg}`, 'error');
        }
    } catch (err) {
        showStatus(statusDiv, `❌ Network error: ${err.message}`, 'error');
    } finally {
        processBtn.disabled = false;
        processBtn.textContent = '⚙️ Process Document';
        progressBar.style.display = 'none';
    }
}

function showStatus(el, message, type) {
    el.style.display = 'block';
    el.textContent = message;
    el.className = 'status-message';
    if (type === 'success') el.classList.add('status-success');
    else if (type === 'error') el.classList.add('status-error');
    else if (type === 'loading') el.classList.add('status-loading');
}
