// Mobile Navigation
document.addEventListener('DOMContentLoaded', function() {
    const hamburger = document.querySelector('.hamburger');
    const navMenu = document.querySelector('.nav-menu');
    const navLinks = document.querySelectorAll('.nav-link');

    // Toggle mobile menu
    if (hamburger) {
        hamburger.addEventListener('click', function() {
            hamburger.classList.toggle('active');
            navMenu.classList.toggle('active');
        });
    }

    // Close mobile menu when clicking on a link
    navLinks.forEach(link => {
        link.addEventListener('click', function() {
            hamburger.classList.remove('active');
            navMenu.classList.remove('active');
        });
    });

    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });

    // Add scroll effect to navbar
    window.addEventListener('scroll', function() {
        const navbar = document.querySelector('.navbar');
        if (window.scrollY > 50) {
            navbar.style.background = 'linear-gradient(135deg, rgba(102, 126, 234, 0.95) 0%, rgba(118, 75, 162, 0.95) 100%)';
            navbar.style.backdropFilter = 'blur(10px)';
        } else {
            navbar.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
            navbar.style.backdropFilter = 'none';
        }
    });

    // Animate elements on scroll
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe all cards and content sections
    document.querySelectorAll('.overview-card, .content-section, .task-box, .info-box').forEach(el => {
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(el);
    });

    // Interactive calculations
    setupCalculations();

    // Quiz functionality
    setupQuiz();
});

// Calculation functions
function setupCalculations() {
    // Tourism intensity calculator
    const intensityForm = document.getElementById('intensity-calculator');
    if (intensityForm) {
        intensityForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const overnight = parseFloat(document.getElementById('overnight-stays').value);
            const population = parseFloat(document.getElementById('population').value);
            
            if (overnight && population) {
                const intensity = (overnight / population).toFixed(1);
                document.getElementById('intensity-result').innerHTML = 
                    `<strong>Tourismusintensität: ${intensity} Übernachtungen pro Einwohner</strong>`;
                
                // Add interpretation
                let interpretation = '';
                if (intensity > 50) {
                    interpretation = 'Sehr hohe Tourismusintensität - Region stark vom Tourismus geprägt';
                } else if (intensity > 20) {
                    interpretation = 'Hohe Tourismusintensität - Tourismus wichtiger Wirtschaftsfaktor';
                } else if (intensity > 5) {
                    interpretation = 'Mittlere Tourismusintensität - Tourismus von Bedeutung';
                } else {
                    interpretation = 'Niedrige Tourismusintensität - Tourismus weniger bedeutend';
                }
                
                document.getElementById('intensity-interpretation').innerHTML = 
                    `<em>${interpretation}</em>`;
            }
        });
    }

    // Economic impact calculator
    const economicForm = document.getElementById('economic-calculator');
    if (economicForm) {
        economicForm.addEventListener('submit', function(e) {
            e.preventDefault();
            const revenue = parseFloat(document.getElementById('tourism-revenue').value);
            const population = parseFloat(document.getElementById('economic-population').value);
            
            if (revenue && population) {
                const perCapita = (revenue / population * 1000).toFixed(0);
                document.getElementById('economic-result').innerHTML = 
                    `<strong>Tourismuseinnahmen pro Einwohner: ${perCapita} Euro</strong>`;
            }
        });
    }
}

// Quiz functionality
function setupQuiz() {
    const quizContainers = document.querySelectorAll('.quiz-container');
    
    quizContainers.forEach(container => {
        const questions = container.querySelectorAll('.quiz-question');
        
        questions.forEach(question => {
            const options = question.querySelectorAll('.quiz-option');
            
            options.forEach(option => {
                option.addEventListener('click', function() {
                    // Remove previous selections
                    options.forEach(opt => opt.classList.remove('selected', 'correct', 'incorrect'));
                    
                    // Mark selected option
                    this.classList.add('selected');
                    
                    // Show correct answer
                    const correctOption = question.querySelector('.quiz-option[data-correct="true"]');
                    if (correctOption) {
                        correctOption.classList.add('correct');
                        
                        if (this !== correctOption) {
                            this.classList.add('incorrect');
                        }
                        
                        // Show explanation
                        const explanation = question.querySelector('.quiz-explanation');
                        if (explanation) {
                            explanation.style.display = 'block';
                        }
                    }
                });
            });
        });
    });
}

// Butler Model Interactive Chart
function createButlerChart() {
    const canvas = document.getElementById('butler-chart');
    if (!canvas) return;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width = 800;
    const height = canvas.height = 400;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    // Set up chart parameters
    const margin = 60;
    const chartWidth = width - 2 * margin;
    const chartHeight = height - 2 * margin;
    
    // Draw axes
    ctx.strokeStyle = '#333';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(margin, height - margin);
    ctx.lineTo(width - margin, height - margin);
    ctx.moveTo(margin, height - margin);
    ctx.lineTo(margin, margin);
    ctx.stroke();
    
    // Draw Butler curve
    const phases = [
        {x: 0, y: 0.9, label: 'Erkundung'},
        {x: 0.15, y: 0.85, label: 'Erschließung'},
        {x: 0.4, y: 0.4, label: 'Entwicklung'},
        {x: 0.65, y: 0.2, label: 'Konsolidierung'},
        {x: 0.8, y: 0.15, label: 'Stagnation'},
        {x: 1, y: 0.1, label: 'Erneuerung/Niedergang'}
    ];
    
    ctx.strokeStyle = '#667eea';
    ctx.lineWidth = 3;
    ctx.beginPath();
    
    phases.forEach((phase, index) => {
        const x = margin + phase.x * chartWidth;
        const y = height - margin - (1 - phase.y) * chartHeight;
        
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
        
        // Draw phase points
        ctx.fillStyle = '#667eea';
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, 2 * Math.PI);
        ctx.fill();
        
        // Add phase labels
        ctx.fillStyle = '#333';
        ctx.font = '12px Inter';
        ctx.textAlign = 'center';
        ctx.fillText(phase.label, x, y - 15);
    });
    
    ctx.stroke();
    
    // Add axis labels
    ctx.fillStyle = '#333';
    ctx.font = '14px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Zeit', width / 2, height - 20);
    
    ctx.save();
    ctx.translate(20, height / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Anzahl Touristen', 0, 0);
    ctx.restore();
}

// Initialize Butler chart when page loads
document.addEventListener('DOMContentLoaded', function() {
    createButlerChart();
});

// Image gallery functionality
function setupImageGallery() {
    const galleryImages = document.querySelectorAll('.gallery-image');
    
    galleryImages.forEach(img => {
        img.addEventListener('click', function() {
            const modal = document.createElement('div');
            modal.className = 'image-modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <span class="close-modal">&times;</span>
                    <img src="${this.src}" alt="${this.alt}" class="modal-image">
                    <p class="modal-caption">${this.alt}</p>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Close modal functionality
            const closeBtn = modal.querySelector('.close-modal');
            closeBtn.addEventListener('click', () => {
                document.body.removeChild(modal);
            });
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    document.body.removeChild(modal);
                }
            });
        });
    });
}

// Progress tracking
function updateProgress() {
    const currentPage = window.location.pathname.split('/').pop() || 'index.html';
    const pages = [
        'index.html',
        'ueberblick.html',
        'gunstfaktoren.html',
        'butler-modell.html',
        'alpen-fallbeispiel.html',
        'berechnungen.html',
        'umweltfolgen.html',
        'soziale-folgen.html',
        'projekt.html',
        'nachhaltigkeit.html',
        'zusammenfassung.html',
        'quellen.html'
    ];
    
    const currentIndex = pages.indexOf(currentPage);
    const progress = ((currentIndex + 1) / pages.length) * 100;
    
    const progressBar = document.querySelector('.progress-bar');
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }
}

// Call progress update on page load
document.addEventListener('DOMContentLoaded', updateProgress);

