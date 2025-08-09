import axios from 'axios';

const API_BASE_URL = 'http://localhost:8010';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000, // 1 minute timeout
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for logging
api.interceptors.request.use(
  (config) => {
    console.log(`API Request: ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('API Request Error:', error);
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    console.log(`API Response: ${response.status} ${response.config.url}`);
    return response;
  },
  (error) => {
    console.error('API Response Error:', error.response?.data || error.message);
    
    // Handle specific error cases
    if (error.response?.status === 404) {
      throw new Error('Resource not found');
    } else if (error.response?.status === 500) {
      throw new Error('Server error occurred');
    } else if (error.code === 'ECONNABORTED') {
      throw new Error('Request timeout');
    } else if (error.code === 'ERR_NETWORK') {
      throw new Error('Network error - please check if the backend is running');
    }
    
    throw error;
  }
);

export const apiService = {
  // Health check
  async checkHealth() {
    try {
      const response = await api.get('/health');
      return response.data;
    } catch (error) {
      throw new Error(`Health check failed: ${error.message}`);
    }
  },

  // Create scraping job
  async createScrapeJob(url, dataType, customInstructions) {
    try {
      const payload = {
        url,
        data_type: dataType,
        custom_instructions: customInstructions || null,
      };
      
      const response = await api.post('/scrape', payload);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to create scrape job: ${error.message}`);
    }
  },

  // Get job status
  async getJobStatus(jobId) {
    try {
      const response = await api.get(`/status/${jobId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get job status: ${error.message}`);
    }
  },

  // Get job result
  async getJobResult(jobId) {
    try {
      const response = await api.get(`/result/${jobId}`);
      return response.data;
    } catch (error) {
      throw new Error(`Failed to get job result: ${error.message}`);
    }
  },

  // Download result file
  async downloadResult(jobId, format) {
    try {
      const response = await api.get(`/download/${jobId}/${format}`, {
        responseType: 'blob',
      });
      
      // Create download link
      const blob = new Blob([response.data]);
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `falcon_parse_result.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
      return true;
    } catch (error) {
      throw new Error(`Failed to download ${format.toUpperCase()} file: ${error.message}`);
    }
  },

  // WebSocket connection for real-time updates
  connectWebSocket(jobId, onMessage, onError) {
    try {
      const wsUrl = `ws://localhost:8010/ws/${jobId}`;
      const socket = new WebSocket(wsUrl);
      
      socket.onopen = () => {
        console.log('WebSocket connected');
      };
      
      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          onMessage(data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };
      
      socket.onerror = (error) => {
        console.error('WebSocket error:', error);
        onError?.(error);
      };
      
      socket.onclose = () => {
        console.log('WebSocket disconnected');
      };
      
      return socket;
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      onError?.(error);
      return null;
    }
  }
};

export default apiService;