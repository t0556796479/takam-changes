export default function Status({ error }) {
  if (!error) return <p className="status">טוען...</p>
  return (
    <p className="status status-error">
      {error.status === 404 ? 'הפריט המבוקש לא נמצא.' : 'לא ניתן לטעון את הנתונים. בדקו שהשרת פועל ונסו שוב.'}
    </p>
  )
}
