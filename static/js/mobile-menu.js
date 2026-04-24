/**
 * Mobile Menu Handler
 * Gère l'affichage/masquage du menu mobile sur les appareils tactiles
 */

document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuBtn = document.querySelector('.mobile-menu-btn');
    const mobileNav = document.querySelector('.mobile-nav');
    
    if (!mobileMenuBtn || !mobileNav) return;
    
    // Toggle menu on button click
    mobileMenuBtn.addEventListener('click', function(e) {
        e.stopPropagation();
        mobileNav.classList.toggle('active');
        
        // Update button appearance
        if (mobileNav.classList.contains('active')) {
            mobileMenuBtn.setAttribute('aria-expanded', 'true');
            mobileMenuBtn.textContent = '✕';
        } else {
            mobileMenuBtn.setAttribute('aria-expanded', 'false');
            mobileMenuBtn.textContent = '☰';
        }
    });
    
    // Close menu when clicking on a link
    const navLinks = mobileNav.querySelectorAll('a');
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            mobileNav.classList.remove('active');
            mobileMenuBtn.setAttribute('aria-expanded', 'false');
            mobileMenuBtn.textContent = '☰';
        });
    });
    
    // Close menu when clicking outside
    document.addEventListener('click', function(e) {
        if (!mobileMenuBtn.contains(e.target) && !mobileNav.contains(e.target)) {
            mobileNav.classList.remove('active');
            mobileMenuBtn.setAttribute('aria-expanded', 'false');
            mobileMenuBtn.textContent = '☰';
        }
    });
    
    // Close menu on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && mobileNav.classList.contains('active')) {
            mobileNav.classList.remove('active');
            mobileMenuBtn.setAttribute('aria-expanded', 'false');
            mobileMenuBtn.textContent = '☰';
            mobileMenuBtn.focus();
        }
    });
});
