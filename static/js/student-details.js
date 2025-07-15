// 学生详情页面JavaScript功能

// 按风险等级过滤学生
function filterStudents(type) {
  const rows = document.querySelectorAll('.student-row');
  const tabs = document.querySelectorAll('.filter-tab');
  let count = 0;

  // 更新选中状态
  tabs.forEach(tab => tab.classList.remove('active'));
  event.target.classList.add('active');

  rows.forEach(row => {
    const risk = row.getAttribute('data-risk');
    let show = false;

    switch (type) {
      case 'all':
        show = true;
        break;
      case 'high':
        show = risk === 'High Risk';
        break;
      case 'medium':
        show = risk === 'Medium Risk';
        break;
      case 'low':
        show = risk !== 'High Risk' && risk !== 'Medium Risk';
        break;
    }

    if (show) {
      row.style.display = '';
      count++;
    } else {
      row.style.display = 'none';
    }
  });

  document.getElementById('currentCount').textContent = count;
}

// 搜索学生
function searchStudents() {
  const searchText = document.getElementById('searchBox').value.toLowerCase();
  const rows = document.querySelectorAll('.student-row');
  let count = 0;

  rows.forEach(row => {
    const studentId = row.getAttribute('data-student-id').toLowerCase();
    if (studentId.includes(searchText)) {
      row.style.display = '';
      count++;
    } else {
      row.style.display = 'none';
    }
  });

  document.getElementById('currentCount').textContent = count;
}

// 导出CSV功能
function exportToCSV() {
  const table = document.getElementById('studentsTable');
  const rows = table.querySelectorAll('tr');
  let csv = [];

  rows.forEach(row => {
    if (row.style.display !== 'none') {
      const cols = row.querySelectorAll('td, th');
      const rowData = Array.from(cols).map(col => {
        return '"' + col.textContent.replace(/"/g, '""') + '"';
      });
      csv.push(rowData.join(','));
    }
  });

  const csvContent = csv.join('\n');
  const blob = new Blob([csvContent], {
    type: 'text/csv;charset=utf-8;'
  });
  const link = document.createElement('a');
  const url = URL.createObjectURL(blob);
  link.setAttribute('href', url);
  link.setAttribute('download', 'student_analysis.csv');
  link.style.visibility = 'hidden';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}