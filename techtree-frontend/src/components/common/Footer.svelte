<script>
  const year = new Date().getFullYear();
</script>

<footer>
  <div class="container">
    <div class="footer-content">
      <div class="footer-section">
        <h3>TechTree</h3>
        <p>Personalized learning paths for technology skills</p>
      </div>

      <div class="footer-section">
        <h3>Quick Links</h3>
        <ul>
          <li><a href="/">Home</a></li>
          <li><a href="/about">About</a></li>
          <li><a href="/help">Help Center</a></li>
          <li><a href="/privacy">Privacy Policy</a></li>
        </ul>
      </div>

      <div class="footer-section">
        <h3>Contact</h3>
        <p>
          <a href="mailto:support@techtree.edu">support@techtree.edu</a>
        </p>
      </div>
    </div>

    <div class="copyright">
      &copy; {year} TechTree Learning. All rights reserved.
    </div>
  </div>
</footer>

<style>
  footer {
    background-color: #333;
    color: white;
    padding: 2rem 0 1rem;
    margin-top: 2rem;
  }

  .container {
    max-width: 1200px;
    margin: 0 auto;
    padding: 0 1rem;
  }

  .footer-content {
    display: flex;
    flex-wrap: wrap;
    justify-content: space-between;
    margin-bottom: 2rem;
  }

  .footer-section {
    flex: 1;
    min-width: 250px;
    margin-bottom: 1.5rem;
  }

  .footer-section h3 {
    font-size: 1.2rem;
    margin-bottom: 1rem;
    color: #4CAF50;
  }

  .footer-section p {
    line-height: 1.6;
  }

  .footer-section ul {
    list-style: none;
    padding: 0;
    margin: 0;
  }

  .footer-section li {
    margin-bottom: 0.5rem;
  }

  .footer-section a {
    color: #ddd;
    text-decoration: none;
    transition: color 0.3s;
  }

  .footer-section a:hover {
    color: #4CAF50;
  }

  .copyright {
    text-align: center;
    padding-top: 1rem;
    border-top: 1px solid #444;
    font-size: 0.9rem;
    color: #aaa;
  }

  @media (max-width: 768px) {
    .footer-content {
      flex-direction: column;
    }

    .footer-section {
      margin-right: 0;
      margin-bottom: 2rem;
    }
  }
</style>