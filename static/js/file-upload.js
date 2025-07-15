// 文件上传交互功能

// 初始化文件上传功能
function initFileUpload() {
  const fileInputs = document.querySelectorAll('input[type="file"]');
  
  fileInputs.forEach(input => {
    // 创建自定义文件选择界面
    createCustomFileInput(input);
    
    // 监听文件选择变化
    input.addEventListener('change', function() {
      handleFileSelection(this);
    });
  });
}

// 创建自定义文件选择界面
function createCustomFileInput(input) {
  const formGroup = input.parentElement;
  const label = formGroup.querySelector('label');
  
  // 隐藏原始文件输入
  input.style.display = 'none';
  
  // 创建自定义按钮
  const customButton = document.createElement('button');
  customButton.type = 'button';
  customButton.className = 'file-select-btn';
  customButton.textContent = '选择文件';
  customButton.onclick = () => input.click();
  
  // 创建文件名显示区域
  const fileNameDisplay = document.createElement('div');
  fileNameDisplay.className = 'file-name-display';
  fileNameDisplay.style.display = 'none';
  
  // 插入到表单组中
  formGroup.appendChild(customButton);
  formGroup.appendChild(fileNameDisplay);
}

// 处理文件选择
function handleFileSelection(input) {
  const formGroup = input.parentElement;
  const customButton = formGroup.querySelector('.file-select-btn');
  const fileNameDisplay = formGroup.querySelector('.file-name-display');
  
  if (input.files && input.files[0]) {
    const fileName = input.files[0].name;
    
    // 隐藏选择按钮
    customButton.style.display = 'none';
    
    // 显示文件名
    fileNameDisplay.innerHTML = `
      <span class="file-name" onclick="changeFile('${input.id}')">${fileName}</span>
      <span class="file-size">(${formatFileSize(input.files[0].size)})</span>
    `;
    fileNameDisplay.style.display = 'block';
  }
}

// 更改文件选择
function changeFile(inputId) {
  const input = document.getElementById(inputId);
  input.click();
}

// 格式化文件大小
function formatFileSize(bytes) {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', initFileUpload);