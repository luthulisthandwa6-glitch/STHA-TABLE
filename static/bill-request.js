document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-bill-form]').forEach(function (form) {
        const button = form.querySelector('button[type="submit"]');
        if (!button) return;

        form.addEventListener('submit', async function (event) {
            event.preventDefault();
            const originalText = button.textContent;
            button.disabled = true;
            button.textContent = 'Sending...';

            try {
                const response = await fetch(form.dataset.billEndpoint, {
                    method: 'POST',
                    headers: { 'Accept': 'application/json' },
                    body: new FormData(form),
                });
                const result = await response.json();
                if (!response.ok || !result.ok) throw new Error(result.error || 'Request failed.');
                button.textContent = 'Bill requested';
                button.classList.add('is-requested');
            } catch (error) {
                button.disabled = false;
                button.textContent = originalText;
                window.alert('We could not send the bill request. Please try again.');
            }
        });
    });
});
