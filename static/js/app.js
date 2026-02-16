/**
 * MagnaAI L/C Platform — Frontend Application
 * Pure JavaScript (no frameworks) with modern async/await
 */

// ═══════════════════════════════════════════════════════════
//  STATE
// ═══════════════════════════════════════════════════════════

const state = {
    pdfFile: null,
    pdfBytes: null,
    extractionResult: null,
    editedFields: {},  // Track edited fields
    hasUnsavedChanges: false,
};

// ═══════════════════════════════════════════════════════════
//  API CLIENT
// ═══════════════════════════════════════════════════════════

const API_BASE = window.location.origin;

async function apiPost(path, body) {
    try {
        const response = await fetch(`${API_BASE}${path}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: response.statusText }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

async function extractDocument(pdfBytesB64, method, provider, model) {
    return apiPost('/extract', {
        pdf_bytes_b64: pdfBytesB64,
        method: method,
        llm_provider: provider,
        model_name: model,
        language: 'en',
    });
}

async function validateDocument(documents) {
    return apiPost('/validate', {
        documents: documents,
        language: 'en',
    });
}

async function verifyField(toolName, args) {
    return apiPost('/verify', {
        tool_name: toolName,
        args: args,
    });
}

async function verifyBatch(fields) {
    return apiPost('/verify/batch', {
        fields: fields,
    });
}

async function chatWithDocument(message, extractedData, pdfText, history) {
    return apiPost('/chat', {
        message: message,
        extracted_data: extractedData,
        pdf_text: pdfText,
        history: history,
        language: 'en',
    });
}

async function deepResearch(query, context) {
    return apiPost('/verify', {
        tool_name: 'deep_research',
        args: { query: query, context: context || '' },
    });
}

// ═══════════════════════════════════════════════════════════
//  UI HELPERS
// ═══════════════════════════════════════════════════════════

function showLoading(text = 'Processing...') {
    document.getElementById('loadingOverlay').classList.remove('hidden');
    document.getElementById('loadingText').textContent = text;
}

function hideLoading() {
    document.getElementById('loadingOverlay').classList.add('hidden');
}

function showStatus(message, type = 'info') {
    const statusCard = document.getElementById('statusCard');
    const statusContent = document.getElementById('statusContent');

    statusCard.style.display = 'block';
    statusContent.innerHTML = `<p class="status-${type}">${message}</p>`;
}

function showError(message) {
    showStatus(`❌ ${message}`, 'error');
    hideLoading();
}

function showSuccess(message) {
    showStatus(`✅ ${message}`, 'success');
}

// ═══════════════════════════════════════════════════════════
//  FILE UPLOAD HANDLING
// ═══════════════════════════════════════════════════════════

function initUpload() {
    const uploadArea = document.getElementById('uploadArea');
    const pdfInput = document.getElementById('pdfInput');

    // Click to upload
    uploadArea.addEventListener('click', () => pdfInput.click());

    // File selected
    pdfInput.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file && file.type === 'application/pdf') {
            handleFileUpload(file);
        } else {
            showError('Please select a valid PDF file');
        }
    });

    // Drag & drop
    uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', () => {
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');

        const file = e.dataTransfer.files[0];
        if (file && file.type === 'application/pdf') {
            pdfInput.files = e.dataTransfer.files;
            handleFileUpload(file);
        } else {
            showError('Please drop a valid PDF file');
        }
    });
}

async function handleFileUpload(file) {
    state.pdfFile = file;

    // Show file info
    const fileInfo = document.getElementById('fileInfo');
    fileInfo.innerHTML = `
        <strong>📄 ${file.name}</strong><br>
        <small>${(file.size / 1024).toFixed(1)} KB</small>
    `;
    fileInfo.classList.remove('hidden');

    // Read file as bytes
    const reader = new FileReader();
    reader.onload = (e) => {
        state.pdfBytes = new Uint8Array(e.target.result);
        document.getElementById('extractionControls').style.display = 'block';
        showStatus('📁 PDF uploaded. Configure settings and click Extract.', 'info');
    };
    reader.readAsArrayBuffer(file);
}

// ═══════════════════════════════════════════════════════════
//  EXTRACTION
// ═══════════════════════════════════════════════════════════

async function handleExtraction() {
    if (!state.pdfBytes) {
        showError('Please upload a PDF first');
        return;
    }

    const method = document.getElementById('methodSelect').value;
    const provider = document.getElementById('llmProvider').value;
    const model = document.getElementById('modelSelect').value;

    // Convert bytes to base64
    const base64 = btoa(String.fromCharCode(...state.pdfBytes));

    showLoading('Extracting L/C fields...');

    try {
        const result = await extractDocument(base64, method, provider, model);

        if (result.success) {
            state.extractionResult = result;
            displayResults(result);
            showSuccess(
                `Extracted ${result.fields_found}/${result.fields_total} fields in ${result.processing_time_ms}ms`
            );
        } else {
            showError(result.error || 'Extraction failed');
        }
    } catch (error) {
        showError(`Extraction failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// ═══════════════════════════════════════════════════════════
//  RESULTS DISPLAY
// ═══════════════════════════════════════════════════════════

function displayResults(result) {
    // Hide welcome, show results
    document.getElementById('welcomeScreen').style.display = 'none';
    document.getElementById('resultsArea').classList.remove('hidden');

    // Extraction Summary
    const summary = document.getElementById('extractionSummary');
    summary.innerHTML = `
        <div class="summary-card">
            <h4>Fields Found</h4>
            <div class="value">${result.fields_found}/${result.fields_total}</div>
        </div>
        <div class="summary-card">
            <h4>Method</h4>
            <div class="value">${result.method_used}</div>
        </div>
        <div class="summary-card">
            <h4>Processing Time</h4>
            <div class="value">${result.processing_time_ms}ms</div>
        </div>
        <div class="summary-card">
            <h4>PDF Type</h4>
            <div class="value">${result.is_scanned ? 'Scanned' : 'Text'}</div>
        </div>
    `;

    // Fields Grid
    const fieldsGrid = document.getElementById('fieldsGrid');
    const fields = result.extracted_data || {};
    const fieldEntries = Object.entries(fields).filter(([k, v]) => v !== null && v !== '');

    if (fieldEntries.length === 0) {
        fieldsGrid.innerHTML = '<p style="color: var(--text-secondary);">No fields extracted.</p>';
    } else {
        fieldsGrid.innerHTML = fieldEntries
            .map(([key, value]) => {
                const label = formatFieldLabel(key);
                const displayValue = String(value).substring(0, 100);
                return `
                    <div class="field-row">
                        <div class="field-label">${label}</div>
                        <div class="field-value">${escapeHtml(displayValue)}</div>
                        <div class="field-confidence conf-high">✓</div>
                    </div>
                `;
            })
            .join('');
    }

    // PDF Preview Tab
    const pdfMetadata = document.getElementById('pdfMetadata');
    pdfMetadata.innerHTML = `
        <strong>PDF Metadata:</strong><br>
        File: ${state.pdfFile.name} (${(state.pdfFile.size / 1024).toFixed(1)} KB)<br>
        Type: ${result.is_scanned ? '📷 Scanned (Image-based)' : '📝 Text-based'}<br>
        Text Length: ${result.pdf_text?.length || 0} characters
    `;

    const pdfTextPreview = document.getElementById('pdfTextPreview');
    pdfTextPreview.value = result.pdf_text || '(No text extracted)';
    pdfTextPreview.rows = 20;

    // Raw Response Tab
    document.getElementById('rawResponse').textContent = JSON.stringify(result, null, 2);
}

function formatFieldLabel(key) {
    return key
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (l) => l.toUpperCase());
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════
//  TABS
// ═══════════════════════════════════════════════════════════

function initTabs() {
    const tabBtns = document.querySelectorAll('.tab-btn');

    tabBtns.forEach((btn) => {
        btn.addEventListener('click', () => {
            const tabName = btn.dataset.tab;

            // Update buttons
            tabBtns.forEach((b) => b.classList.remove('active'));
            btn.classList.add('active');

            // Update content
            document.querySelectorAll('.tab-content').forEach((tc) => tc.classList.remove('active'));
            document.getElementById(`tab-${tabName}`).classList.add('active');
        });
    });
}

// ═══════════════════════════════════════════════════════════
//  MODEL SELECTION
// ═══════════════════════════════════════════════════════════

function initModelSelection() {
    const providerSelect = document.getElementById('llmProvider');
    const modelSelect = document.getElementById('modelSelect');

    providerSelect.addEventListener('change', () => {
        const provider = providerSelect.value;

        if (provider === 'gemini') {
            modelSelect.innerHTML = `
                <option value="gemini-2.5-flash">Gemini 2.5 Flash</option>
                <option value="gemini-2.5-pro">Gemini 2.5 Pro</option>
                <option value="gemini-2.0-flash">Gemini 2.0 Flash</option>
                <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
            `;
        } else {
            modelSelect.innerHTML = `
                <option value="gpt-4o">GPT-4o</option>
                <option value="gpt-4o-mini">GPT-4o Mini</option>
            `;
        }
    });
}

// ═══════════════════════════════════════════════════════════
//  VALIDATION
// ═══════════════════════════════════════════════════════════

async function handleValidation() {
    if (!state.extractionResult || !state.extractionResult.extracted_data) {
        showError('Please extract a document first');
        return;
    }

    showLoading('Running validation checks...');

    try {
        const documents = {
            letter_of_credit: state.extractionResult.extracted_data,
        };

        const result = await validateDocument(documents);

        if (result.success) {
            displayValidationResults(result);
            showSuccess(`Validation complete: ${result.passed_checks}/${result.total_checks} checks passed`);
        } else {
            showError(result.error || 'Validation failed');
        }
    } catch (error) {
        showError(`Validation failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

function displayValidationResults(result) {
    const container = document.getElementById('validationResults');
    const checks = result.checks || [];

    if (checks.length === 0) {
        container.innerHTML = '<p class="empty-state">No validation checks available.</p>';
        return;
    }

    container.innerHTML = checks
        .map((check) => {
            const status = check.passed ? 'pass' : (check.severity === 'warning' ? 'warning' : 'fail');
            const badge = check.passed ? 'pass' : (check.severity === 'warning' ? 'warning' : 'fail');
            const icon = check.passed ? '✅' : (check.severity === 'warning' ? '⚠️' : '❌');

            return `
                <div class="validation-check ${status}">
                    <div class="validation-check-header">
                        <span class="validation-check-title">${icon} ${check.rule_name}</span>
                        <span class="validation-check-badge badge-${badge}">
                            ${check.passed ? 'PASS' : (check.severity === 'warning' ? 'WARNING' : 'FAIL')}
                        </span>
                    </div>
                    <div class="validation-check-message">${escapeHtml(check.message)}</div>
                </div>
            `;
        })
        .join('');
}

// ═══════════════════════════════════════════════════════════
//  VERIFICATION
// ═══════════════════════════════════════════════════════════

const FIELD_VERIFICATION_MAP = {
    beneficiary_bank_swift: 'verify_swift_code',
    correspondent_bank_swift: 'verify_swift_code',
    advising_bank_swift: 'verify_swift_code',
    port_loading: 'verify_port',
    port_destination: 'verify_port',
    port_of_loading: 'verify_port',
    port_of_destination: 'verify_port',
    hs_code: 'verify_hs_code',
    goods_hs_code: 'verify_hs_code',
    beneficiary_name: 'verify_company',
    applicant_name: 'check_sanctions',
};

async function handleVerifyAll() {
    if (!state.extractionResult || !state.extractionResult.extracted_data) {
        showError('Please extract a document first');
        return;
    }

    const fieldsToVerify = [];
    const extractedData = state.extractionResult.extracted_data;

    // Build verification requests
    for (const [fieldKey, value] of Object.entries(extractedData)) {
        if (!value || value === '') continue;

        const toolName = FIELD_VERIFICATION_MAP[fieldKey];
        if (!toolName) continue;

        const args = buildVerifyArgs(toolName, value);
        fieldsToVerify.push({ field_key: fieldKey, tool_name: toolName, args: args, value: value });
    }

    if (fieldsToVerify.length === 0) {
        showError('No verifiable fields found in the extracted data');
        return;
    }

    showLoading(`Verifying ${fieldsToVerify.length} fields...`);

    try {
        const batchRequest = fieldsToVerify.map(f => ({ tool_name: f.tool_name, args: f.args }));
        const result = await verifyBatch(batchRequest);

        displayVerificationResults(fieldsToVerify, result.results || [], result.errors || []);
        showSuccess(`Verified ${result.results?.length || 0} fields`);
    } catch (error) {
        showError(`Verification failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

function buildVerifyArgs(toolName, value) {
    if (toolName === 'verify_swift_code') return { code: value };
    if (toolName === 'verify_port') return { port_name: value };
    if (toolName === 'verify_hs_code') return { code: value };
    if (toolName === 'check_sanctions') return { party_name: value };
    if (toolName === 'verify_company') return { company_name: value };
    return { field_value: value };
}

function displayVerificationResults(fields, results, errors) {
    const container = document.getElementById('verificationResults');

    if (fields.length === 0) {
        container.innerHTML = '<p class="empty-state">No verifiable fields found.</p>';
        return;
    }

    container.innerHTML = fields
        .map((field, index) => {
            const result = results[index] || {};
            const error = errors[index];

            const verified = result.verified || false;
            const statusClass = verified ? 'verified' : 'failed';
            const statusText = verified ? '✅ Verified' : '❌ Failed';
            const message = result.message || error?.error || 'No response';

            return `
                <div class="verification-field">
                    <div class="verification-field-header">
                        <div class="verification-field-info">
                            <div class="verification-field-label">${formatFieldLabel(field.field_key)}</div>
                            <div class="verification-field-value">${escapeHtml(String(field.value).substring(0, 60))}</div>
                        </div>
                    </div>
                    <div class="verification-result ${statusClass}">
                        <strong>${statusText}</strong>: ${escapeHtml(message)}
                        ${result.confidence ? `<br><small>Confidence: ${(result.confidence * 100).toFixed(0)}%</small>` : ''}
                    </div>
                </div>
            `;
        })
        .join('');
}

// ═══════════════════════════════════════════════════════════
//  CHAT
// ═══════════════════════════════════════════════════════════

const chatHistory = [];

async function handleChatSend() {
    const input = document.getElementById('chatInput');
    const message = input.value.trim();

    if (!message) return;

    if (!state.extractionResult) {
        showError('Please extract a document first before chatting');
        return;
    }

    // Add user message to UI
    addChatMessage('user', message);
    input.value = '';

    showLoading('Thinking...');

    try {
        const extractedData = state.extractionResult.extracted_data || {};
        const pdfText = state.extractionResult.pdf_text || '';

        const result = await chatWithDocument(message, extractedData, pdfText, chatHistory);

        // Add to history
        chatHistory.push({ role: 'user', content: message });
        chatHistory.push({ role: 'assistant', content: result.message });

        // Add assistant message to UI
        addChatMessage('assistant', result.message || 'Sorry, I could not generate a response.');
    } catch (error) {
        addChatMessage('assistant', `Error: ${error.message}`);
    } finally {
        hideLoading();
    }
}

function addChatMessage(role, content) {
    const container = document.getElementById('chatMessages');

    // Remove welcome message if present
    const welcome = container.querySelector('.chat-welcome');
    if (welcome) welcome.remove();

    const messageDiv = document.createElement('div');
    messageDiv.className = `chat-message ${role}`;
    messageDiv.innerHTML = `<div class="chat-bubble">${escapeHtml(content)}</div>`;

    container.appendChild(messageDiv);
    container.scrollTop = container.scrollHeight;
}

// ═══════════════════════════════════════════════════════════
//  DEEP SEARCH
// ═══════════════════════════════════════════════════════════

async function handleDeepSearch() {
    const query = document.getElementById('searchQuery').value.trim();

    if (!query) {
        showError('Please enter a search query');
        return;
    }

    const searchDoc = document.getElementById('searchDocumentCheck').checked;
    const searchExternal = document.getElementById('searchExternalCheck').checked;

    let context = '';

    // Include document context if requested
    if (searchDoc && state.extractionResult) {
        const pdfText = state.extractionResult.pdf_text || '';
        const extractedData = JSON.stringify(state.extractionResult.extracted_data || {}, null, 2);
        context = `Document Context:\n${pdfText.substring(0, 3000)}\n\nExtracted Data:\n${extractedData}`;
    }

    showLoading('Researching with Perplexity + Exa...');

    try {
        const result = await deepResearch(query, context);

        displaySearchResults(result, query);
        showSuccess('Research complete');
    } catch (error) {
        showError(`Search failed: ${error.message}`);
    } finally {
        hideLoading();
    }
}

function displaySearchResults(result, query) {
    const container = document.getElementById('searchResults');

    const verified = result.verified || false;
    const message = result.message || 'No results found';
    const details = result.details || {};

    let html = `
        <div class="search-result">
            <div class="search-result-header">
                <div class="search-result-title">🔍 ${escapeHtml(query)}</div>
                <div class="search-result-source">${result.source || 'Deep Research'}</div>
            </div>
            <div class="search-result-content">
                <strong>${verified ? '✅ Verified' : 'ℹ️ Research Result'}:</strong><br>
                ${escapeHtml(message)}
            </div>
    `;

    // Add source URLs if available
    if (details.source_urls && details.source_urls.length > 0) {
        html += `
            <div class="search-result-links">
                <strong>Sources:</strong><br>
                ${details.source_urls.slice(0, 5).map(url => `<a href="${url}" target="_blank">${url}</a>`).join('<br>')}
            </div>
        `;
    }

    // Add Exa results if available
    if (details.exa_results && details.exa_results.length > 0) {
        html += `
            <div class="search-result-links">
                <strong>Web Results:</strong><br>
                ${details.exa_results.slice(0, 5).map(r => `<a href="${r.url}" target="_blank">${r.title}</a>`).join('<br>')}
            </div>
        `;
    }

    html += '</div>';
    container.innerHTML = html;
}

// ═══════════════════════════════════════════════════════════
//  INITIALIZATION
// ═══════════════════════════════════════════════════════════

document.addEventListener('DOMContentLoaded', () => {
    initUpload();
    initTabs();
    initModelSelection();

    // Extract button
    document.getElementById('extractBtn').addEventListener('click', handleExtraction);

    // Validation button
    document.getElementById('runValidationBtn').addEventListener('click', handleValidation);

    // Verification button
    document.getElementById('verifyAllBtn').addEventListener('click', handleVerifyAll);

    // Chat
    document.getElementById('chatSendBtn').addEventListener('click', handleChatSend);
    document.getElementById('chatInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleChatSend();
    });

    // Deep Search
    document.getElementById('searchBtn').addEventListener('click', handleDeepSearch);
    document.getElementById('searchQuery').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') handleDeepSearch();
    });

    console.log('MagnaAI L/C Platform initialized with all features');
});
