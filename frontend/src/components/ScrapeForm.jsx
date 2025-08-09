import React, { useState } from 'react';
import { Globe, Search, Loader2 } from 'lucide-react';

const DATA_TYPE_OPTIONS = [
  { value: 'custom', label: 'Custom (specify below)' },
  { value: 'contact_information', label: 'Contact Information' },
  { value: 'social_media_links', label: 'Social Media Links & Profiles' },
  { value: 'product_listings', label: 'Product Listings' },
  { value: 'news_articles', label: 'News Articles' },
  { value: 'job_postings', label: 'Job Postings' },
  { value: 'event_listings', label: 'Event Listings' },
  { value: 'pricing_tables', label: 'Pricing Tables' },
  { value: 'company_details', label: 'Company Details' },
  { value: 'testimonials', label: 'Testimonials & Reviews' },
  { value: 'team_members', label: 'Team Members & Staff' },
  { value: 'menu_items', label: 'Menu Items' },
];

const ScrapeForm = ({ onSubmit, isLoading }) => {
  const [formData, setFormData] = useState({
    url: '',
    dataType: 'custom',
    customInstructions: ''
  });
  
  const [errors, setErrors] = useState({});

  const validateForm = () => {
    const newErrors = {};
    
    // Validate URL
    if (!formData.url.trim()) {
      newErrors.url = 'URL is required';
    } else {
      try {
        new URL(formData.url);
      } catch {
        newErrors.url = 'Please enter a valid URL (including http:// or https://)';
      }
    }
    
    // Validate data type
    if (formData.dataType === 'custom' && !formData.customInstructions.trim()) {
      newErrors.customInstructions = 'Please specify what data to extract when using custom type';
    }
    
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }

    const dataType = formData.dataType === 'custom' 
      ? formData.customInstructions.trim()
      : formData.dataType;

    onSubmit({
      url: formData.url.trim(),
      dataType,
      customInstructions: formData.dataType === 'custom' ? formData.customInstructions.trim() : null
    });
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    
    // Clear error when user starts typing
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: '' }));
    }
  };

  const handleUrlChange = (e) => {
    let url = e.target.value;
    
    // Auto-add https:// if no protocol specified and it looks like a domain
    if (url && !url.startsWith('http://') && !url.startsWith('https://') && url.includes('.')) {
      if (!url.includes(' ') && url.length > 3) {
        // Only auto-add https if it looks like a valid domain
        const domainPattern = /^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\..*$/;
        if (domainPattern.test(url)) {
          url = 'https://' + url;
        }
      }
    }
    
    handleInputChange('url', url);
  };

  return (
    <div className="card">
      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label htmlFor="url" className="form-label">
            <Globe size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
            Website URL
          </label>
          <input
            id="url"
            type="url"
            className={`form-input ${errors.url ? 'error' : ''}`}
            placeholder="https://example.com"
            value={formData.url}
            onChange={handleUrlChange}
            disabled={isLoading}
          />
          {errors.url && <div className="status-message status-error">{errors.url}</div>}
        </div>

        <div className="form-group">
          <label htmlFor="dataType" className="form-label">
            <Search size={16} style={{ display: 'inline', marginRight: '0.5rem' }} />
            Data Type to Extract
          </label>
          <select
            id="dataType"
            className="form-select"
            value={formData.dataType}
            onChange={(e) => handleInputChange('dataType', e.target.value)}
            disabled={isLoading}
          >
            {DATA_TYPE_OPTIONS.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {formData.dataType === 'custom' && (
          <div className="form-group">
            <label htmlFor="customInstructions" className="form-label">
              Describe What Data to Extract
            </label>
            <textarea
              id="customInstructions"
              className={`form-textarea ${errors.customInstructions ? 'error' : ''}`}
              placeholder="e.g., Extract product names, prices, and availability status from the product listing page"
              value={formData.customInstructions}
              onChange={(e) => handleInputChange('customInstructions', e.target.value)}
              disabled={isLoading}
            />
            {errors.customInstructions && (
              <div className="status-message status-error">{errors.customInstructions}</div>
            )}
          </div>
        )}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={isLoading}
          style={{ width: '100%' }}
        >
          {isLoading ? (
            <>
              <Loader2 size={20} className="spinner" />
              Processing...
            </>
          ) : (
            <>
              <Search size={20} />
              Extract Data
            </>
          )}
        </button>
      </form>
    </div>
  );
};

export default ScrapeForm;