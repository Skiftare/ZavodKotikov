function initReviewsCarousel() {
    const reviews = document.querySelectorAll('.review-item');
    const indicators = document.querySelectorAll('.indicator');
    const prevBtn = document.querySelector('.review-prev');
    const nextBtn = document.querySelector('.review-next');
    let currentReview = 0;

    function showReview(index) {
        reviews.forEach(review => review.classList.remove('active'));
        indicators.forEach(indicator => indicator.classList.remove('active'));

        reviews[index].classList.add('active');
        indicators[index].classList.add('active');
        currentReview = index;
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            let nextIndex = (currentReview + 1) % reviews.length;
            showReview(nextIndex);
        });
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            let prevIndex = (currentReview - 1 + reviews.length) % reviews.length;
            showReview(prevIndex);
        });
    }

    indicators.forEach((indicator, index) => {
        indicator.addEventListener('click', () => showReview(index));
    });
}

// Запускаем когда DOM загружен
document.addEventListener('DOMContentLoaded', initReviewsCarousel);