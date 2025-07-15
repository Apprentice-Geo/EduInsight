// 等待页面JavaScript功能

// 全局变量
let stepIndex = 1;
let steps = [];
let userId = '';

// 模拟进度更新
function updateProgress() {
  if (stepIndex < steps.length - 1) {
    steps[stepIndex].classList.add('active');
    stepIndex++;
  }
}

// 检查分析状态
function checkStatus() {
  fetch(`/api/status/${userId}`)
    .then(response => response.json())
    .then(data => {
      if (data.status === 'completed') {
        // 完成所有步骤
        steps.forEach(step => step.classList.add('active'));
        setTimeout(() => {
          window.location.href = `/results/${userId}`;
        }, 1500);
      } else if (data.status === 'error') {
        document.querySelector('.status-text').innerHTML = 
          '❌ 分析过程中出现错误，请返回重新上传文件';
      } else {
        // 更新进度
        updateProgress();
        // 5秒后再次检查
        setTimeout(checkStatus, 5000);
      }
    })
    .catch(error => {
      console.error('Error checking status:', error);
      // 出错也继续重试
      setTimeout(checkStatus, 8000);
    });
}

// 初始化页面
function initializePage(userIdParam) {
  userId = userIdParam;
  steps = document.querySelectorAll('.step');
  
  // 开始检查状态
  checkStatus();
  
  // 每3秒更新一次进度显示
  setInterval(updateProgress, 3000);
}

// 页面加载完成后初始化
window.onload = function() {
  // userId 将通过模板传递
  // 这个函数会在HTML中被调用
};