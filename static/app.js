document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('form[onsubmit]').forEach(form => {
    form.addEventListener('submit', event => {
      if (form.getAttribute('onsubmit') && !confirm('Are you sure you want to close this auction?')) event.preventDefault();
    });
  });
});
